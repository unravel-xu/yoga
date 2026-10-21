"""Parameter Execute DAT. Reset is explicit and reproducible."""
def onPulse(par):
    if par.name == "Reset":
        owner = par.owner
        owner.par.Resetserial = int(owner.par.Resetserial)+1
    return
