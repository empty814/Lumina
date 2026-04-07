"""
LocalProvider：使用本地 mlx-lm 模型进行推理（默认 Provider）。

并发策略（Continuous Batching，仿 tLLM AsyncEngine）：

  旧方案（Dynamic Batching）：
    - 收集短窗口内的请求，串行跑完整个 stream_generate
    - 请求 B 必须等请求 A 全部生成完才开始 → TTFT(B) = O(max_tokens_A × latency)

  新方案（Continuous Batching）：
    - prefill_queue：新请求入队
    - _active：正在 decode 的 _RequestSlot，每个持有 KV cache + step_iter
    - 调度循环每次迭代：
        1. 从 prefill_queue 取新请求执行 prefill + 首 token，put 到 slot.token_queue
        2. 对 _active 中已存在的请求各推进 1 步，put 到 slot.token_queue
        3. 结束标志（None）put 到已完成请求的 queue
    - 消费方从 token_queue.get() 流式消费，天然线程安全、无竞争
    - 效果：TTFT(B) ≈ prefill(A) + 1 step，而非等 A 全部完成
"""
import asyncio
import threading
from dataclasses import dataclass, field
from typing import AsyncIterator, Iterator, List, Optional, Tuple
import uuid

import mlx.core as mx
from mlx_lm import load
from mlx_lm.generate import generate_step, cache as mlx_cache
from mlx_lm.sample_utils import make_sampler

from .base import BaseProvider

# 每次迭代最多接入的新 prefill 请求数
_MAX_NEW_PREFILL_PER_ITER = 2


@dataclass
class _RequestSlot:
    """一个请求的完整生命周期状态。"""
    request_id: str
    prompt_tokens: mx.array
    max_tokens: int
    temperature: float

    # 调度线程把 token 文本 put 进来，None = 结束，Exception = 错误
    # asyncio.Queue：跨线程安全（run_coroutine_threadsafe put）+ 协程 get
    token_queue: asyncio.Queue = field(default_factory=asyncio.Queue)

    # 调度线程写入（在 prefill 完成后）
    step_iter: Optional[Iterator[Tuple[int, mx.array]]] = None
    _token_ids: List[int] = field(default_factory=list)
    n_tokens: int = 0
    done: bool = False


class LocalProvider(BaseProvider):
    def __init__(self, model_path: str):
        self.model_path = model_path
        self._model = None
        self._tokenizer = None
        self._prefill_queue: Optional[asyncio.Queue] = None
        self._not_empty: Optional[asyncio.Event] = None
        self._worker_task: Optional[asyncio.Task] = None
        self._active: List[_RequestSlot] = []
        self._active_lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ── 生命周期 ──────────────────────────────────────────────────────────────

    def load(self):
        self._model, self._tokenizer = load(self.model_path)
        mx.eval(self._model.parameters())

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    def _ensure_worker(self):
        if self._prefill_queue is None:
            self._prefill_queue = asyncio.Queue()
            self._not_empty = asyncio.Event()
        if self._worker_task is None or self._worker_task.done():
            self._loop = asyncio.get_running_loop()
            self._worker_task = asyncio.create_task(self._scheduler())

    # ── Prompt 构建 ───────────────────────────────────────────────────────────

    def _build_prompt_tokens(self, system: str, user_text: str) -> mx.array:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ]
        prompt_str = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        return mx.array(self._tokenizer.encode(prompt_str))

    # ── EOS token ids ─────────────────────────────────────────────────────────

    @property
    def _eos_ids(self) -> set:
        eos = self._tokenizer.eos_token_id
        if isinstance(eos, list):
            return set(eos)
        return {eos} if eos is not None else set()

    # ── 同步推理（executor 线程）─────────────────────────────────────────────

    def _put_token(self, slot: _RequestSlot, value) -> None:
        """线程安全地往 asyncio Queue put 值（在 executor 线程中调用）。"""
        asyncio.run_coroutine_threadsafe(slot.token_queue.put(value), self._loop)

    def _do_prefill(self, slot: _RequestSlot) -> None:
        """
        执行 prefill + 生成首 token。
        结果通过 slot.token_queue 传递。
        """
        sampler = make_sampler(temp=slot.temperature, top_p=0.9)
        prompt_cache = mlx_cache.make_prompt_cache(self._model)
        eos_ids = self._eos_ids
        try:
            step_iter = generate_step(
                prompt=slot.prompt_tokens,
                model=self._model,
                max_tokens=slot.max_tokens,
                sampler=sampler,
                prompt_cache=prompt_cache,
            )
            slot.step_iter = step_iter
            token_id, _ = next(step_iter)

            if token_id in eos_ids:
                slot.done = True
                self._put_token(slot, None)  # 立即结束
                return

            slot._token_ids = [token_id]
            text = self._tokenizer.decode([token_id])
            slot.n_tokens = 1
            self._put_token(slot, text)

            if slot.n_tokens >= slot.max_tokens:
                slot.done = True
                self._put_token(slot, None)

        except StopIteration:
            slot.done = True
            self._put_token(slot, None)
        except Exception as e:
            slot.done = True
            self._put_token(slot, e)

    def _advance_one(self, slot: _RequestSlot) -> None:
        """推进一个 decode step，结果 put 到 token_queue。"""
        eos_ids = self._eos_ids
        try:
            token_id, _ = next(slot.step_iter)
        except StopIteration:
            slot.done = True
            self._put_token(slot, None)
            return
        except Exception as e:
            slot.done = True
            self._put_token(slot, e)
            return

        if token_id in eos_ids:
            slot.done = True
            self._put_token(slot, None)
            return

        prev_text = self._tokenizer.decode(slot._token_ids)
        slot._token_ids.append(token_id)
        new_text = self._tokenizer.decode(slot._token_ids)
        delta = new_text[len(prev_text):]
        slot.n_tokens += 1
        self._put_token(slot, delta)

        if slot.n_tokens >= slot.max_tokens:
            slot.done = True
            self._put_token(slot, None)

    def _run_one_iter(self, prefill_list: List[_RequestSlot]) -> None:
        """
        单次调度迭代（executor 线程）：
          1. 先快照当前 _active（Phase 2 只处理这些）
          2. prefill 新请求，加入 _active
          3. decode 快照中的请求
          4. 清理完成请求
        """
        # Phase 1 前先快照（本轮新 prefill 的请求不参与 Phase 2）
        with self._active_lock:
            decode_batch = [s for s in self._active if not s.done]

        # Phase 1: prefill
        newly_active = []
        for slot in prefill_list:
            self._do_prefill(slot)
            if not slot.done:
                newly_active.append(slot)

        with self._active_lock:
            self._active.extend(newly_active)

        # Phase 2: decode（快照，不含本轮新 prefill）
        for slot in decode_batch:
            if not slot.done:
                self._advance_one(slot)

        # 清理
        with self._active_lock:
            self._active = [s for s in self._active if not s.done]

    # ── 调度主循环 ────────────────────────────────────────────────────────────

    async def _scheduler(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            with self._active_lock:
                has_active = bool(self._active)

            if not has_active and self._prefill_queue.empty():
                self._not_empty.clear()
                await self._not_empty.wait()

            prefill_list: List[_RequestSlot] = []
            while len(prefill_list) < _MAX_NEW_PREFILL_PER_ITER:
                try:
                    prefill_list.append(self._prefill_queue.get_nowait())
                except asyncio.QueueEmpty:
                    break

            await loop.run_in_executor(None, self._run_one_iter, prefill_list)

    # ── 公共接口 ──────────────────────────────────────────────────────────────

    async def generate_stream(
        self,
        user_text: str,
        system: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        if not self.is_ready:
            raise RuntimeError("LocalProvider not loaded. Call load() first.")

        self._ensure_worker()

        system_str = system or "You are a helpful assistant."
        prompt_tokens = self._build_prompt_tokens(system_str, user_text)

        slot = _RequestSlot(
            request_id=uuid.uuid4().hex,
            prompt_tokens=prompt_tokens,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        await self._prefill_queue.put(slot)
        self._not_empty.set()

        # 从 token_queue 流式消费：None = 结束，Exception = 错误
        while True:
            item = await slot.token_queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item
