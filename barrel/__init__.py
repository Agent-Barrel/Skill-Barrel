"""barrel -- the unit loop execution layer built on step2step.

`barrel.core.unitloop` runs a roadmap of units, giving each unit one fresh
step2step session and judging it with deterministic gates. The package is
import-light: nothing here starts a session or reads the environment at import
time.
"""
