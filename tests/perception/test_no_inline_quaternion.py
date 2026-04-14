"""D-10 invariant guard.

Only `OrientedBox3D.to_wire` in `src/perception/types.py` is allowed to
construct the literal ``"quaternion":`` JSON key on the wire. Every other
backend, emitter, or adapter in ``src/`` MUST call ``to_wire()`` rather than
hand-rolling a quaternion dict literal.

This test is a CI-enforced grep invariant. It fails loudly the moment any
future commit reintroduces inline quaternion serialization outside the
canonical serializer, citing offender file:line so the violator is obvious.
"""

import pathlib
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[2]


def test_no_inline_quaternion_literal():
    """D-10: only OrientedBox3D.to_wire constructs 'quaternion':"""
    result = subprocess.run(
        ["grep", "-rn", '"quaternion":', str(REPO / "src")],
        capture_output=True, text=True,
    )
    hits = result.stdout.strip().splitlines() if result.stdout.strip() else []
    allowed = [h for h in hits if "types.py" in h]
    disallowed = [h for h in hits if "types.py" not in h]
    assert not disallowed, (
        f"D-10 violation: {len(disallowed)} inline \"quaternion\": literal(s) outside "
        f"OrientedBox3D.to_wire. First offenders:\n" + "\n".join(disallowed[:5])
    )
    assert len(allowed) == 1, (
        f"Expected exactly 1 'quaternion':' hit in types.py (inside to_wire()); "
        f"got {len(allowed)}:\n" + "\n".join(allowed)
    )
