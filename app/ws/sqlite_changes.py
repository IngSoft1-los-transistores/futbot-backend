"""Notificaciones del SO para escritores SQLite de otros procesos.

No consulta la base periódicamente. Registrar el watcher antes del snapshot
inicial evita perder un commit entre la lectura y la suscripción.
"""
import asyncio
from pathlib import Path
from threading import Event

from watchfiles._rust_notify import RustNotify


class SQLiteChanges:
    def __init__(self, bind):
        database = bind.url.database
        if bind.dialect.name != 'sqlite' or not database or database == ':memory:':
            raise ValueError('El stream requiere SQLite en archivo; otras bases necesitan un adaptador de notificaciones')
        path = Path(database).resolve()
        self.paths = {str(path), str(path) + '-wal', str(path) + '-journal'}
        self.stop = Event()
        # Backend nativo, sin force_polling ni timeouts que consulten la base.
        self.watcher = RustNotify([str(path.parent)], False, False, 0, False, False)
        self.pending = None

    async def wait(self):
        while not self.stop.is_set():
            self.pending = asyncio.create_task(asyncio.to_thread(self.watcher.watch, 50, 10, 0, self.stop))
            changes = await asyncio.shield(self.pending)
            self.pending = None
            if isinstance(changes, set) and any(path in self.paths for _, path in changes):
                return
            if changes in ('stop', 'signal'):
                return

    async def close(self):
        self.stop.set()
        if self.pending is not None:
            await self.pending
        self.watcher.close()
