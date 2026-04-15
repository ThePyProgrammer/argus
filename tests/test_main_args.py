"""DET-METRICS-03: --labeled-eval-set CLI flag reservation test.

Per CONTEXT D-10: the flag is parsed but passing it MUST raise
NotImplementedError with the exact message
"Labeled eval set ingestion arrives in a future milestone".

Revision 2026-04-15 (WARNING 5): subprocess invocation is the ONLY
acceptable path for this test — any argument-parsing-only fallback would
silently skip verification of the actual NotImplementedError raise.
Subprocess timeout is generous (60s) for an argparse + early-return code
path; ``main()`` checks ``args.labeled_eval_set`` and raises BEFORE any
heavy init (coordinator / bridge / scene loading).
"""
import subprocess
import sys


def test_labeled_eval_set_flag_raises_not_implemented(tmp_path):
    """--labeled-eval-set <path> must raise NotImplementedError + exit non-zero."""
    dummy = tmp_path / "eval.json"
    dummy.write_text("{}", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "src.main", "--labeled-eval-set", str(dummy)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    # Expect non-zero exit (Python raises → traceback → sys.exit(1)).
    assert proc.returncode != 0, (
        f"expected non-zero exit; stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    combined = proc.stdout + proc.stderr
    assert (
        "Labeled eval set ingestion arrives in a future milestone" in combined
    ), f"expected CONTEXT D-10 message in output; got: {combined!r}"
    # Sanity: the traceback must identify NotImplementedError (not some other
    # error raised by the argparse layer or an unrelated import).
    assert "NotImplementedError" in combined, (
        f"expected NotImplementedError in traceback; got: {combined!r}"
    )
