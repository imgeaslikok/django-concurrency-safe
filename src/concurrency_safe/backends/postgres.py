import time

from django.db import connection

from ..hashing import key_to_int64


class PostgresAdvisoryLockBackend:
    """
    PostgreSQL advisory lock backend.

    This backend provides mutual exclusion using PostgreSQL's advisory lock
    mechanism. Advisory locks are application-defined locks identified by a
    64-bit integer key and managed entirely by PostgreSQL.

    Key properties
    --------------
    - Connection-scoped: the lock is bound to the current database connection.
      If the connection is closed (e.g. process crash), PostgreSQL automatically
      releases the lock.
    - Non-transactional: advisory locks are independent of transactions unless
      explicitly using the transaction-scoped variants.
    - Global visibility: all workers connected to the same database compete
      for the same lock ID.

    Why advisory locks?
    -------------------
    Advisory locks allow coordinating critical sections without locking a
    specific table row. This is ideal for protecting operations identified
    by business keys (e.g. "stock:ABC", "withdraw:user:42") rather than
    individual database records.

    Timeout behavior
    ----------------
    - timeout=None:
        Blocks indefinitely until the lock is acquired.

    - timeout=float:
        Attempts to acquire the lock repeatedly until the timeout expires.
        Uses pg_try_advisory_lock to avoid blocking the connection.

    Thread/process safety
    ---------------------
    Safe across multiple processes and machines as long as they share the
    same PostgreSQL instance.

    Limitations
    -----------
    - Requires PostgreSQL.
    - Lock scope is limited to a single database cluster.
    """

    def acquire(self, key: str, timeout: float | None) -> bool:
        """
        Attempt to acquire an advisory lock for the given key.

        Parameters
        ----------
        key : str
            Application-defined lock key. This will be hashed into a stable
            signed 64-bit integer, as required by PostgreSQL.

        timeout : float | None
            Maximum time to wait for the lock, in seconds.

            - None: block indefinitely until acquired.
            - float: retry until timeout expires.

        Returns
        -------
        bool
            True if the lock was successfully acquired.
            False if the timeout expired before acquisition.

        Notes
        -----
        This method uses pg_try_advisory_lock when timeout is provided to avoid
        blocking the database connection, allowing explicit timeout control.
        """
        lock_id = key_to_int64(key)

        # Blocking acquisition: PostgreSQL waits until the lock is available.
        if timeout is None:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_lock(%s);", [lock_id])
            return True

        deadline = time.monotonic() + timeout

        # Poll using pg_try_advisory_lock to respect timeout.
        while time.monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(%s);", [lock_id])
                acquired = cursor.fetchone()[0]

            if acquired:
                return True

            # Small sleep prevents tight loop and reduces DB load.
            time.sleep(0.05)

        return False

    def release(self, key: str) -> None:
        """
        Release the advisory lock for the given key.

        Parameters
        ----------
        key : str
            The same key used during acquisition.

        Notes
        -----
        PostgreSQL silently ignores unlock requests for locks not held by
        the current connection, so this operation is safe to call in finally
        blocks without additional checks.
        """
        lock_id = key_to_int64(key)

        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s);", [lock_id])