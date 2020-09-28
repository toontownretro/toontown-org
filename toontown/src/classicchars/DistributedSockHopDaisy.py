"""DistributedSockHopDaisy module: contains the DistributedSockHopDaisy class"""

from pandac.PandaModules import *
import DistributedCCharBase
from direct.directnotify import DirectNotifyGlobal
from direct.fsm import ClassicFSM, State
from direct.fsm import State
from toontown.classicchars import DistributedDaisy
import CharStateDatas
from toontown.toonbase import ToontownGlobals
from toontown.toonbase import TTLocalizer
import DistributedCCharBase

class DistributedSockHopDaisy(DistributedDaisy.DistributedDaisy):
    """DistributedSockHopDaisy class"""

    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedSockHopDaisy")

    def __init__(self, cr):
        try:
            self.DistributedSockHopDaisy_initialized
        except:
            self.DistributedSockHopDaisy_initialized = 1
            DistributedCCharBase.DistributedCCharBase.__init__(self, cr,
                                                               TTLocalizer.SockHopDaisy,
                                                               'shdd')
            self.fsm = ClassicFSM.ClassicFSM(self.getName(),
                            [State.State('Off',
                                         self.enterOff,
                                         self.exitOff,
                                         ['Neutral']),
                             State.State('Neutral',
                                         self.enterNeutral,
                                         self.exitNeutral,
                                         ['Walk']),
                             State.State('Walk',
                                         self.enterWalk,
                                         self.exitWalk,
                                         ['Neutral']),
                             ],
                             # Initial State
                             'Off',
                             # Final State
                             'Off',
                             )

            self.fsm.enterInitialState()
            
            # We want her to show up as Daisy
            self.nametag.setName(TTLocalizer.Daisy)
            
    def walkSpeed(self):
        return ToontownGlobals.DaisySpeed
