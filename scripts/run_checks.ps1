# Shared quality gates. Add -Audit for online dependency checks.
param([switch]$Audit)
if ($Audit) { python scripts/run_checks.py --audit }
else { python scripts/run_checks.py }
exit $LASTEXITCODE
