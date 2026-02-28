import hashlib


def key_to_int64(key: str) -> int:
    """
    Convert a string key into a stable signed 64-bit integer.

    PostgreSQL advisory locks require a BIGINT identifier. This function
    deterministically maps an arbitrary string into the valid BIGINT range.

    Why hashing is necessary
    ------------------------
    Advisory locks operate on integers, but application lock keys are usually
    meaningful strings (e.g. "stock:ABC", "user:42"). We hash the string to:

    - ensure consistent lock IDs across processes
    - avoid collisions in typical usage
    - fit PostgreSQL's required 64-bit signed integer range

    Implementation details
    ----------------------
    We use BLAKE2b with an 8-byte digest:

    - Fast and cryptographically strong
    - Fixed-length output (64 bits)
    - Stable across Python versions and platforms

    PostgreSQL expects a signed BIGINT (-2^63 to 2^63-1), so we convert the
    unsigned hash into the signed range.

    Parameters
    ----------
    key : str
        Arbitrary lock key string.

    Returns
    -------
    int
        Signed 64-bit integer suitable for pg_advisory_lock.
    """
    digest = hashlib.blake2b(
        key.encode("utf-8"),
        digest_size=8,  # 8 bytes = 64 bits
    ).digest()

    value = int.from_bytes(
        digest,
        byteorder="big",
        signed=False,
    )

    # Convert unsigned -> signed int64 range
    if value >= 2**63:
        value -= 2**64

    return value
