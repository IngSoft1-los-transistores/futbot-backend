"""Broadcast entre hilos del proceso sin disco ni sondeo del estado."""
import asyncio
from dataclasses import dataclass
from threading import RLock

from app.schemas.match_state import MatchState


@dataclass(eq=False)
class Subscription:
    match_id: str
    session_id: str
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue
    active: bool = True
    revoked: bool = False

    def deliver(self, message):
        if not self.active or (self.revoked and message['type'] != 'revoked'):
            return
        # Cada mensaje es un snapshot completo. Un cliente lento conserva el
        # último, sin acumular ticks ni bloquear al motor o a otros clientes.
        if self.queue.full():
            self.queue.get_nowait()
        self.queue.put_nowait(message)


class ConnectionManager:
    def __init__(self):
        self._subscriptions: set[Subscription] = set()
        self._lock = RLock()

    def subscribe(self, match_id: str, session_id: str) -> Subscription:
        subscription = Subscription(match_id, session_id, asyncio.get_running_loop(), asyncio.Queue(maxsize=1))
        with self._lock:
            self._subscriptions.add(subscription)
        return subscription

    def unsubscribe(self, subscription):
        with self._lock:
            subscription.active = False
            self._subscriptions.discard(subscription)

    def _notify(self, subscription, message):
        try:
            subscription.loop.call_soon_threadsafe(subscription.deliver, message)
        except RuntimeError:
            # El loop del cliente ya cerró; no afecta al tick ni a otros sockets.
            self.unsubscribe(subscription)

    def broadcast(self, state: MatchState):
        message = {'type': 'state', 'state': state.model_dump(mode='json')}
        with self._lock:
            for subscription in tuple(self._subscriptions):
                if subscription.match_id == str(state.match_id) and not subscription.revoked:
                    self._notify(subscription, message)

    def revoke_session(self, session_id: str):
        with self._lock:
            for subscription in tuple(self._subscriptions):
                if subscription.session_id == session_id:
                    subscription.revoked = True
                    self._notify(subscription, {'type': 'revoked'})


manager = ConnectionManager()
