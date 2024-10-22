from direct.gui.DirectGui import *
from pandac.PandaModules import *
from direct.directnotify import DirectNotifyGlobal
from toontown.toonbase import ToontownGlobals
from toontown.toonbase import TTLocalizer
from direct.task.Task import Task

class BankGui(DirectFrame):
    """
    Create a gui that allows the localtoon to deposit and withdraw money
    from his bank. This gui includes a switch for allowing (or not allowing)
    withdrawals.
    """

    notify = DirectNotifyGlobal.directNotify.newCategory("BankGui")

    def __init__(self, doneEvent, allowWithdraw=1):
        DirectFrame.__init__(self,
                             relief = None,
                             geom = DGG.getDefaultDialogGeom(),
                             geom_color = ToontownGlobals.GlobalDialogColor,
                             geom_scale = (1.33,1,1.1),
                             pos = (0,0,0),
                             )
        self.initialiseoptions(BankGui)
        # Send this when we are done so whoever made us can get a callback
        self.doneEvent = doneEvent
        # Positive indicates a deposit, negative indicates a withdraw
        self.__transactionAmount = 0

        buttons = loader.loadModel('phase_3/models/gui/dialog_box_buttons_gui')
        jarGui = loader.loadModel("phase_3.5/models/gui/jar_gui")
        arrowGui = loader.loadModel("phase_3/models/gui/create_a_toon_gui")
        bankModel = loader.loadModel("phase_5.5/models/estate/jellybeanBank.bam")
        # If we set this on the entire bank, the billboard jellybeans goes away
        # Let's just set it on the pig, the rest of the bank looks ok
        #bankModel.find("**/pig").setDepthWrite(0)
        #bankModel.find("**/pig").setDepthTest(0)
        bankModel.setDepthWrite(1)
        bankModel.setDepthTest(1)
        bankModel.find("**/jellybeans").setDepthWrite(0)
        bankModel.find("**/jellybeans").setDepthTest(0)

        # Init buttons
        okImageList = (buttons.find('**/ChtBx_OKBtn_UP'),
                       buttons.find('**/ChtBx_OKBtn_DN'),
                       buttons.find('**/ChtBx_OKBtn_Rllvr'))
        cancelImageList = (buttons.find('**/CloseBtn_UP'),
                           buttons.find('**/CloseBtn_DN'),
                           buttons.find('**/CloseBtn_Rllvr'))
        arrowImageList = (arrowGui.find("**/CrtATn_R_Arrow_UP"),
                          arrowGui.find("**/CrtATn_R_Arrow_DN"),
                          arrowGui.find("**/CrtATn_R_Arrow_RLVR"),
                          arrowGui.find("**/CrtATn_R_Arrow_UP"))

        self.cancelButton = DirectButton(
            parent = self,
            relief = None,
            image = cancelImageList,
            pos = (-0.2, 0, -0.4),
            text = TTLocalizer.BankGuiCancel,
            text_scale = 0.06,
            text_pos = (0,-0.1),
            command = self.__cancel,
            )
        self.okButton = DirectButton(
            parent = self,
            relief = None,
            image = okImageList,
            pos = (0.2, 0, -0.4),
            text = TTLocalizer.BankGuiOk,
            text_scale = 0.06,
            text_pos = (0,-0.1),
            command = self.__requestTransaction,
            )

        self.jarDisplay = DirectLabel(
            parent = self,
            relief = None,
            pos = (-0.4,0,0),
            scale = 0.7,
            text = str(base.localAvatar.getMoney()),
            text_scale = 0.2,
            text_fg = (0.95, 0.95, 0, 1),
            text_shadow = (0, 0, 0, 1),
            text_pos = (0, -0.1, 0),
            image = jarGui.find("**/Jar"),
            text_font = ToontownGlobals.getSignFont(),
            )
        self.bankDisplay = DirectLabel(
            parent = self,
            relief = None,
            pos = (0.4,0,0),
            scale = 0.9,
            text = str(base.localAvatar.getBankMoney()),
            text_scale = 0.2,
            text_fg = (0.95, 0.95, 0, 1),
            text_shadow = (0, 0, 0, 1),
            text_pos = (0, -0.1, 0),
            geom = bankModel,
            geom_scale = 0.08,
            geom_pos = (0, 10, -0.26),
            geom_hpr = (0, 0, 0),
            text_font = ToontownGlobals.getSignFont(),
            )

        self.depositArrow = DirectButton(
            parent = self,
            relief = None,
            image = arrowImageList,
            image_scale = (1,1,1),
            image3_color = Vec4(0.6,0.6,0.6,0.25),
            pos = (0.01, 0, 0.15),
            )
        self.withdrawArrow = DirectButton(
            parent = self,
            relief = None,
            image = arrowImageList,
            image_scale = (-1,1,1),
            image3_color = Vec4(0.6,0.6,0.6,0.25),
            pos = (-0.01, 0, -0.15),
            )

        self.depositArrow.bind(DGG.B1PRESS, self.__depositButtonDown)
        self.depositArrow.bind(DGG.B1RELEASE, self.__depositButtonUp)

        self.withdrawArrow.bind(DGG.B1PRESS, self.__withdrawButtonDown)
        self.withdrawArrow.bind(DGG.B1RELEASE, self.__withdrawButtonUp)

        self.accept("bankAsleep", self.__cancel)
        self.accept(localAvatar.uniqueName("moneyChange"), self.__moneyChange)
        self.accept(localAvatar.uniqueName("bankMoneyChange"), self.__bankMoneyChange)

        if allowWithdraw:
            self.depositArrow.setPos(0.01, 0, 0.15)
            self.withdrawArrow.setPos(-0.01, 0, -0.15)
        else:
            self.depositArrow.setPos(0,0,0)
            self.withdrawArrow.hide()

        buttons.removeNode()
        jarGui.removeNode()
        arrowGui.removeNode()

        # Refresh the status of the gui
        # Give it a 0 for a transaction so it does not change the values
        self.__updateTransaction(0)

    def destroy(self):
        taskMgr.remove(self.taskName("runCounter"))
        self.ignore(localAvatar.uniqueName("moneyChange"))
        self.ignore(localAvatar.uniqueName("bankMoneyChange"))
        DirectFrame.destroy(self)

    def __cancel(self):
        assert(self.notify.debug("transaction cancelled"))
        messenger.send(self.doneEvent, [0])

    def __requestTransaction(self):
        assert(self.notify.debug("requestTransaction: amount: %s" %
                                 self.__transactionAmount))
        messenger.send(self.doneEvent, [self.__transactionAmount])

    def __updateTransaction(self, amount):
        # Determine if we have hit a limit
        hitLimit = 0
        # Update the running total for this transaction
        self.__transactionAmount += amount
        # See how much money we have now
        jarMoney = base.localAvatar.getMoney()
        maxJarMoney = base.localAvatar.getMaxMoney()
        bankMoney = base.localAvatar.getBankMoney()
        maxBankMoney = base.localAvatar.getMaxBankMoney()

        # Apply more limits--these might have changed if our money
        # changed externally (e.g. due to a resistance phrase).
        self.__transactionAmount = min(self.__transactionAmount, jarMoney)
        self.__transactionAmount = min(self.__transactionAmount, maxBankMoney - bankMoney)
        self.__transactionAmount = -min(-self.__transactionAmount, maxJarMoney - jarMoney)
        self.__transactionAmount = -min(-self.__transactionAmount, bankMoney)

        # Compute the new money for jar and bank
        newJarMoney = (jarMoney - self.__transactionAmount)
        newBankMoney = (bankMoney + self.__transactionAmount)
        # Now see if any of the buttons need to be disabled
        if (newJarMoney <= 0) or (newBankMoney >= maxBankMoney):
            self.depositArrow['state'] = DGG.DISABLED
            hitLimit = 1
        else:
            self.depositArrow['state'] = DGG.NORMAL
        if (newBankMoney <= 0) or (newJarMoney >= maxJarMoney):
            self.withdrawArrow['state'] = DGG.DISABLED
            hitLimit = 1
        else:
            self.withdrawArrow['state'] = DGG.NORMAL
        # Update the text on the jar and bank with the new values
        self.jarDisplay['text'] = str(newJarMoney)
        self.bankDisplay['text'] = str(newBankMoney)
        # Return the new states of our balances
        return (hitLimit, newJarMoney, newBankMoney, self.__transactionAmount)

    def __runCounter(self, task):
        if ((task.time - task.prevTime) < task.delayTime):
            return Task.cont
        else:
            # Set the delay lower each time to increase the speed
            # But clamp it so it does not get rediculous
            task.delayTime = max(0.05, task.delayTime * 0.75)
            task.prevTime = task.time
            # Update the gui, which returns the new state
            hitLimit, jar, bank, trans = self.__updateTransaction(task.delta)
            # If we hit a limit on the jar or bank, return done
            if hitLimit:
                return Task.done
            else:
                return Task.cont

    def __depositButtonUp(self, event):
        messenger.send('wakeup')
        taskMgr.remove(self.taskName("runCounter"))

    def __depositButtonDown(self, event):
        messenger.send('wakeup')
        task = Task(self.__runCounter)
        task.delayTime = 0.4
        task.prevTime = 0.0
        task.delta = 1
        hitLimit, jar, bank, trans = self.__updateTransaction(task.delta)
        if not hitLimit:
            taskMgr.add(task, self.taskName("runCounter"))

    def __withdrawButtonUp(self, event):
        messenger.send('wakeup')
        taskMgr.remove(self.taskName("runCounter"))

    def __withdrawButtonDown(self, event):
        messenger.send('wakeup')
        task = Task(self.__runCounter)
        task.delayTime = 0.4
        task.prevTime = 0.0
        task.delta = -1
        hitLimit, jar, bank, trans = self.__updateTransaction(task.delta)
        if not hitLimit:
            taskMgr.add(task, self.taskName("runCounter"))

    def __moneyChange(self, money):
        self.__updateTransaction(0)

    def __bankMoneyChange(self, bankMoney):
        self.__updateTransaction(0)
