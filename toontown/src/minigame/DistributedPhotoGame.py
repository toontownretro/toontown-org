
from direct.directnotify import DirectNotifyGlobal
from pandac.PandaModules import *
from toontown.toonbase.ToonBaseGlobal import *
from DistributedMinigame import *
from direct.distributed.ClockDelta import *
from direct.interval.IntervalGlobal import *
from direct.fsm import ClassicFSM, State
from direct.fsm import State
from toontown.toonbase import ToontownGlobals
from toontown.toonbase import ToontownTimer
from direct.task.Task import Task
import math
from toontown.toon import ToonHead
import PhotoGameGlobals
from direct.gui.DirectGui import *
from toontown.toonbase import TTLocalizer
from toontown.golf import BuildGeometry
from toontown.toon import Toon
from toontown.toon import ToonDNA
from direct.interval.IntervalGlobal import *
import random
from direct.showbase import PythonUtil
import math
import time
from toontown.makeatoon import NameGenerator
from otp.otpbase import OTPGlobals
from toontown.battle import BattleParticles
from toontown.minigame import PhotoGameBase

# some constants

WORLD_SCALE = 2.
FAR_PLANE_DIST = 600 * WORLD_SCALE
STAGE_Z_OFFSET = 7.0

GOODROWS = 13 #make odd
BADROWS = 4 #make even
RAYSPREADX = 0.08
RAYSPREADY = 0.06

ZOOMRATIO = 0.4
#ZOOMRATIO = 0.5
ZOOMTIME = 0.5
WANTDOTS = 1

NUMSTARS = PhotoGameGlobals.NUMSTARS
STARSIZE = 0.06


VIEWSIZEX = (GOODROWS - BADROWS) * RAYSPREADX
VIEWSIZEY = (GOODROWS - BADROWS) * RAYSPREADY


def toRadians(angle):
    return angle * 2.0 * math.pi / 360.0

def toDegrees(angle):
    return angle * 360.0 / (2.0 * math.pi)



class DistributedPhotoGame(DistributedMinigame, PhotoGameBase.PhotoGameBase):

    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedPhotoGame")

    font = ToontownGlobals.getToonFont()

    LOCAL_PHOTO_MOVE_TASK = "localPhotoMoveTask"


    # keyboard controls
    FIRE_KEY  = "control"
    UP_KEY    = "arrow_up"
    DOWN_KEY  = "arrow_down"
    LEFT_KEY  = "arrow_left"
    RIGHT_KEY = "arrow_right"

    INTRO_TASK_NAME = "PhotoGameIntro"
    INTRO_TASK_NAME_CAMERA_LERP = "PhotoGameIntroCamera"



    def __init__(self, cr):
        DistributedMinigame.__init__(self, cr)
        PhotoGameBase.PhotoGameBase.__init__(self)

        # NOTE: it would be nice to be able to kick off the gameFSM
        # before DistributedMinigame goes into its 'game' state
        # currently, gameFSM *is* DistributedMinigame's 'game'
        # state; entering the 'game' state resets the gameFSM =(

        #self.notify.info((1,2,3))
        #self.notify.debug((1,2,3))
        #self.notify.warning((1,2,3))
        #self.notify.error((1,2,3))

        self.gameFSM = ClassicFSM.ClassicFSM('DistributedPhotoGame',
                               [
                                State.State('off',
                                            self.enterOff,
                                            self.exitOff,
                                            ['aim']),
                                State.State('aim',
                                            self.enterAim,
                                            self.exitAim,
                                            ['showResults','cleanup', 'zoom']),
                                State.State('zoom',
                                            self.enterZoom,
                                            self.exitZoom,
                                            ['showResults','cleanup', 'aim']),
                                State.State('showResults',
                                            self.enterShowResults,
                                            self.exitShowResults,
                                            ['cleanup']),
                                State.State('cleanup',
                                            self.enterCleanup,
                                            self.exitCleanup,
                                            []),
                                ],
                               # Initial State
                               'off',
                               # Final State
                               'cleanup',
                               )

        # Add our game ClassicFSM to the framework ClassicFSM
        self.addChildGameFSM(self.gameFSM)

        self.tripod = None

        # these keep track of the local tripod controls
        # since there are multiple inputs tied to each
        # of these (buttons and keypresses), they are
        # incremented for every button or keypress
        # that is active
        self.leftPressed = 0
        self.rightPressed = 0
        self.upPressed = 0
        self.downPressed = 0

        # this is set to true when the local cannon is moving
        self.photoMoving = 0

        self.introSequence = None
        #base.pg = self

        self.subjects = []
        self.scenery = []
        #self.subjectNode = None
        self.subjectNode = render.attachNewNode("subjects")
        self.subjectTracks = {}
        self.nameCounter = 0
        self.zoomedView = 0
        self.zoomFlip = 1
        self.cameraTrack = None

        self.assignments = []
        self.currentAssignment = 0
        #self.assignmentPanel = None
        #self.activeAssignments = []
        self.assignmentPanels = []

        self.toonList = []

        self.assignmentDataDict = {}
        self.starDict = {}
        self.starParentDict = {}

        self.textureBuffers = []

        self.filmCount = 20

        self.edgeUp = 0
        self.edgeRight = 0
        self.edgeDown = 0
        self.edgeLeft = 0

        self.scorePanel = None

        #for index in range(ONSCREENASSIGNMENTS):
        #    self.activeAssignments.append(None)

    def getTitle(self):
        return TTLocalizer.PhotoGameTitle

    def getInstructions(self):
        return TTLocalizer.PhotoGameInstructions

    def getMaxDuration(self):
        return PhotoGameGlobals.GAME_TIME

    def load(self):
        self.notify.debug("load")
        DistributedMinigame.load(self)
        PhotoGameBase.PhotoGameBase.load(self)

        self.filmCount = self.data["FILMCOUNT"]

        self.safeZoneStorageDNAFile = self.data["DNA_TRIO"][0]#"phase_4/dna/storage_TT_sz.dna"
        self.storageDNAFile = self.data["DNA_TRIO"][1] #"phase_4/dna/storage_TT.dna"
        self.dnaFile = self.data["DNA_TRIO"][2] #"phase_4/dna/toontown_central_sz.dna"

        self.dnaStore = DNAStorage()

        loader.loadDNAFile(self.dnaStore, "phase_4/dna/storage.dna")
        loader.loadDNAFile(self.dnaStore, self.storageDNAFile)
        loader.loadDNAFile(self.dnaStore, self.safeZoneStorageDNAFile)
        node =  loader.loadDNAFile(self.dnaStore, self.dnaFile)

        self.scene = hidden.attachNewNode(node)

        self.construct()

        # load the jellybean jar image
        # this model is 'owned' (read: destroyed) by PurchaseBase

        purchaseModels = loader.loadModel(
                "phase_4/models/gui/purchase_gui")
        #self.jarImage = purchaseModels.find("**/Jar")

        self.filmImage = loader.loadModel("phase_4/models/minigames/photogame_filmroll")

        self.filmImage.reparentTo(hidden)

        self.tripodModel = loader.loadModel(
            "phase_4/models/minigames/toon_cannon")

        # reward display
        self.filmPanel = DirectLabel(
            parent = hidden,
            relief = None,
            pos = (1.16, 0.0, 0.45),
            scale = .65,
            text = str(self.filmCount),
            text_scale = 0.2,
            text_fg = (0.95, 0.95, 0, 1),
            text_pos = (0.08, -0.15),
            text_font = ToontownGlobals.getSignFont(),
            image = self.filmImage,
            image_scale = Point3(1.0, 0.0, 0.85),
            )
        self.filmPanelTitle = DirectLabel(
            parent = self.filmPanel,
            relief = None,
            pos = (0.08, 0, 0.04),
            scale = .08,
            text = TTLocalizer.PhotoGameFilm,
            text_fg = (.95,.95,0,1),
            text_shadow = (0,0,0,1),
            )

        self.music = base.loadMusic(
            "phase_4/audio/bgm/MG_cannon_game.mid"
            )

        self.sndPhotoMove = base.loadSfx(\
                                 "phase_4/audio/sfx/MG_cannon_adjust.mp3")
        self.sndPhotoFire = base.loadSfx(\
                                 "phase_4/audio/sfx/MG_cannon_fire_alt.mp3")
        self.sndWin        = base.loadSfx(\
                                 "phase_4/audio/sfx/MG_win.mp3")

        self.sndFilmTick = base.loadSfx(\
                                 "phase_4/audio/sfx/Photo_instamatic.mp3")

        self.timer = ToontownTimer.ToontownTimer()
        self.timer.posInTopRightCorner()
        self.timer.hide()

        self.viewfinderNode = base.aspect2d.attachNewNode("camera node")
        #self.viewfinderNode.setP(90)
        self.viewfinderNode.setTransparency(TransparencyAttrib.MAlpha)
        self.viewfinderNode.setDepthWrite(1)
        self.viewfinderNode.setDepthTest(1)
        self.viewfinderNode.setY(-1.0)
        #self.buildGeomNode = self.viewfinderNode.attachNewNode("buildgeom node")
        #self.buildGeomNode.setP(90)

        self.screenSizeMult = 0.5
        #self.viewfinderNode.setX(mpos.getX() * self.screenSizeX)

        self.screenSizeX = (base.a2dRight - base.a2dLeft) * self.screenSizeMult
        self.screenSizeZ = (base.a2dTop - base.a2dBottom) * self.screenSizeMult

        viewfinderImage = loader.loadModel("phase_4/models/minigames/photo_game_viewfinder")
        viewfinderImage.reparentTo(self.viewfinderNode)
        viewfinderImage.setScale(0.55,1.0,0.55)

        #BuildGeometry.addSquareGeom(self.buildGeomNode, VIEWSIZEX, VIEWSIZEY, Vec4(1.0,1.0,1.0,0.1))

        self.blackoutNode = base.aspect2d.attachNewNode("blackout node")
        self.blackoutNode.setP(90)
        BuildGeometry.addSquareGeom(self.blackoutNode, self.screenSizeX * 2.2, self.screenSizeZ * 2.2, Vec4(1.0,1.0,1.0,1.0))
        self.blackoutNode.setTransparency(TransparencyAttrib.MAlpha)
        self.blackoutNode.setColorScale(0.0,0.0,0.0,0.5)
        self.blackoutNode.setDepthWrite(1)
        self.blackoutNode.setDepthTest(1)
        self.blackoutNode.hide()



        self.subjectToon = Toon.Toon()

        self.addSound('zoom', "Photo_zoom.mp3", "phase_4/audio/sfx/")

        self.addSound('snap', "Photo_shutter.mp3", "phase_4/audio/sfx/")


    def __setupCapture(self):

        #self.captureNode = base.aspect2d.attachNewNode("capture node")#
        #self.captureNode.setP(90)#
        #BuildGeometry.addSquareGeom(self.captureNode, self.screenSizeX * 0.5, self.screenSizeZ * 0.5, Vec4(1.0,1.0,1.0,1.0))#
        #self.captureNode.setDepthWrite(1)#
        #self.captureNode.setDepthTest(1)#
        #self.captureNode.setPos(-0.8,-200.0,0.5)#

        #self.textureBuffer = base.win.makeTextureBuffer("Photo Capture", 128,128)
        #self.captureCam = base.makeCamera(self.textureBuffer)
        self.captureCam = NodePath(Camera("CaptureCamera"))
        self.captureCam.reparentTo(self.pointer)

        self.captureLens = PerspectiveLens()

        self.captureOutFOV = (VIEWSIZEX / self.screenSizeX) * self.outFov * 0.5
        self.captureZoomFOV = (VIEWSIZEX / self.screenSizeX) * self.zoomFov * 0.5

        self.captureLens.setFov(self.captureOutFOV)
        self.captureLens.setAspectRatio(1.33)
        self.captureCam.node().setLens(self.captureLens)


        #tempTexture = self.textureBuffer.getTexture()#
        #self.captureNode.setTexture(tempTexture)#

        #self.textureBuffer.setActive(0)

    def __removeCapture(self):
        #self.captureNode.removeNode()#

        del self.captureCam
        del self.captureLens
        #base.graphicsEngine.removeWindow(self.textureBuffer)
        #del self.textureBuffer

    def unload(self):
        self.notify.debug("unload")
        DistributedMinigame.unload(self)

        if self.cameraTrack:
            self.cameraTrack.finish()
            self.cameraTrack = None

        self.__removeCapture()

        for textureBuffer in self.textureBuffers:
            base.graphicsEngine.removeWindow(textureBuffer)
        del self.textureBuffers

        self.viewfinderNode.removeNode()
        self.blackoutNode.removeNode()

        for key in self.assignmentDataDict:
            assignmentData = self.assignmentDataDict[key]
            assignmentData[7].delete()

        del self.assignmentDataDict

        self.assignments = []

        for subject in self.subjects:
            subject.delete()
        self.subjects = []

        self.subjectToon.delete()

        self.destruct()

        for scenery in self.scenery:
            scenery.removeNode()
        self.scenery = None

        self.subjectNode.removeNode()
        self.subjectNode = None

        self.sky.removeNode()
        del self.sky


        self.photoRoot = None

        #no scene
        self.scene.removeNode()
        del self.scene

        self.pointer.removeNode()

        # get rid of original cannon model
        self.tripodModel.removeNode()
        del self.tripodModel



        for panel in self.assignmentPanels:
            panel.destroy()

        self.assignmentPanels = []
        if self.scorePanel:
            self.scorePanel.destroy()

        self.starDict = {}
        self.starParentDict = {}


        self.filmPanel.destroy()
        del self.filmPanel
        self.filmImage.removeNode()
        del self.filmImage

        # Get rid of audio
        del self.music
        del self.sndPhotoMove
        del self.sndPhotoFire
        del self.sndWin
        del self.sndFilmTick

        self.tripod.removeNode()
        del self.tripod
        del self.swivel

        # Goodbye timer
        self.timer.destroy()
        del self.timer

        # remove our game ClassicFSM from the framework ClassicFSM
        self.removeChildGameFSM(self.gameFSM)
        del self.gameFSM

        self.ignoreAll()

    def onstage(self):
        self.notify.debug("Onstage")
        DistributedMinigame.onstage(self)

        # show everything
        self.__createTripod()
        self.tripod.reparentTo(render)

        self.tripod.hide()




        self.__loadToonInTripod(self.localAvId)

        camera.reparentTo(render)
        self.__oldCamFar = base.camLens.getFar()
        base.camLens.setFar(FAR_PLANE_DIST)

        self.__setupSubjects()

        self.__startIntro()

        # Iris in
        #base.transitions.irisIn(0.4)
        base.transitions.irisIn()

        # Start music
        base.playMusic(self.music, looping = 1, volume = 0.8)

        #orgFov = base.camLens.getFov()
        #self.outFov = VBase2(orgFov[0] * 1.0, orgFov[1] * 1.0)
        #self.zoomFov = VBase2(orgFov[0] * ZOOMRATIO, orgFov[1] * ZOOMRATIO)

        orgFov = base.camLens.getFov()
        self.outFov = orgFov.getX()
        self.zoomFov = orgFov.getX() * ZOOMRATIO

        self.currentFov = self.outFov

        self.__setupCapture()



    def offstage(self):
        self.notify.debug("offstage")
        self.sky.reparentTo(hidden)

        self.scene.reparentTo(hidden)

        for avId in self.avIdList:
            av = self.getAvatar(avId)
            if av:
                # show the dropshadow again
                av.dropShadow.show()
                # restore the LODs
                av.resetLOD()

        self.__stopIntro()
        base.camLens.setFar(self.__oldCamFar)
        self.timer.reparentTo(hidden)
        self.filmPanel.reparentTo(hidden)
        DistributedMinigame.offstage(self)
        for key in self.subjectTracks:
            track = self.subjectTracks[key][0]
            track.pause()
            del track
        self.subjectTracks = {}
        base.localAvatar.laffMeter.start()

        del self.soundTable


    def __setupCollisions(self):
        self.queue = CollisionHandlerQueue()
        self.traverser = CollisionTraverser('traverser name')

        self.rayArray = []

        vRange = (GOODROWS-BADROWS)/2


        for row in range(-(GOODROWS/2),(GOODROWS/2) + 1):
            for column in range(-(GOODROWS/2),(GOODROWS/2) + 1):
                goodRange = range(-((GOODROWS-BADROWS)/2),((GOODROWS-BADROWS)/2) + 1)
                rayQuality = "g"
                if (not (row in goodRange)) or (not (column in goodRange)):
                    rayQuality = "l"
                    if row > vRange:
                        rayQuality = "r"
                    if column > vRange:
                        rayQuality = "t"
                    if column < -vRange:
                        rayQuality = "b"

                columnString = ("+%s" % (column))
                if column < 0:
                    columnString = ("%s" % (column))
                rowString = ("+%s" % (row))
                if row < 0:
                    rowString = ("%s" % (row))


                pickerNode=CollisionNode('%s %s %s' % (rowString, columnString, rayQuality))
                pickerNP=camera.attachNewNode(pickerNode)
                pickerNode.setFromCollideMask(GeomNode.getDefaultCollideMask())
                pickerRay=CollisionRay()
                pickerNode.addSolid(pickerRay)

                self.rayArray.append((row,column,pickerNode, pickerNP, pickerRay))

                self.traverser.addCollider(pickerNP, self.queue)
                #pickerNP.setHpr(hDif,vDif,0)

        if WANTDOTS:

            self.markerDict = {}


            for rayEntry in self.rayArray:
                 markerNode = self.viewfinderNode.attachNewNode("marker Node")
                 BuildGeometry.addSquareGeom(markerNode, 0.01, 0.01, Vec4(1.0,1.0,1.0,1.0))
                 markerNode.setX((RAYSPREADX * rayEntry[0]))
                 markerNode.setY((RAYSPREADY * rayEntry[1]))
                 markerNode.setDepthWrite(1)
                 markerNode.setZ(2.0)

                 self.markerDict[(rayEntry[0], rayEntry[1])] = (markerNode)


        self.lensNode = LensNode('photo taker')
        self.lensNode.setLens(base.camLens)

    def __moveViewfinder(self, task):
        if base.mouseWatcherNode.hasMouse():
            mpos=base.mouseWatcherNode.getMouse()
            self.viewfinderNode.setX(mpos.getX() * self.screenSizeX)
            self.viewfinderNode.setZ(mpos.getY() * self.screenSizeZ)

            horzAngle = (self.viewfinderNode.getX() / self.screenSizeX) * 0.5 * base.camLens.getFov()[0]
            vertAngle = (self.viewfinderNode.getZ() / self.screenSizeZ) * 0.5 * base.camLens.getFov()[1]

            horzPointFlat = (self.viewfinderNode.getX() / self.screenSizeX)
            vertPointFlat = (self.viewfinderNode.getZ() / self.screenSizeZ)

            horzLength = base.camLens.getFov()[0] * 0.5
            vertLength = base.camLens.getFov()[1] * 0.5

            horzRadianLength = toRadians(horzLength)
            vertRadianLength = toRadians(vertLength)

            hMRadian = math.atan( horzPointFlat * math.tan(horzRadianLength) )
            vMRadian = math.atan( vertPointFlat * math.tan(vertRadianLength) )

            hMDegree = toDegrees(hMRadian)
            vMDegree = toDegrees(vMRadian)

            self.pointer.setH(-hMDegree)
            self.pointer.setP(vMDegree)

            newRight = 0
            newLeft = 0
            newUp = 0
            newDown = 0

            if self.viewfinderNode.getX() > (self.screenSizeX * .95):
                newRight = 1

            if self.viewfinderNode.getX() < (self.screenSizeX * -0.95):
                newLeft = 1

            if self.viewfinderNode.getZ() > (self.screenSizeZ * .95):
                newUp = 1

            if self.viewfinderNode.getZ() < (self.screenSizeZ * -0.95):
                newDown = 1

            if (not self.edgeRight) and newRight:
                self.edgeRight = 1
                self.__rightPressed()
            elif self.edgeRight and  (not newRight):
                self.edgeRight = 0
                self.__rightReleased()

            if (not self.edgeLeft) and newLeft:
                self.edgeLeft = 1
                self.__leftPressed()
            elif self.edgeLeft and  (not newLeft):
                self.edgeLeft = 0
                self.__leftReleased()

            if (not self.edgeUp) and newUp:
                self.edgeUp = 1
                self.__upPressed()
            elif self.edgeUp and  (not newUp):
                self.edgeUp = 0
                self.__upReleased()

            if (not self.edgeDown) and newDown:
                self.edgeDown = 1
                self.__downPressed()
            elif self.edgeDown and  (not newDown):
                self.edgeDown = 0
                self.__downReleased()

            #self.notify.debug("Screen angles H:%s V:%s" % (self.swivel.getH(), self.swivel.getP()))
            #self.notify.debug("Viewfinder to screen angles with math H:%s V:%s" % (hMDegree, vMDegree))




        return task.cont




    def __testCollisions(self):

        self.notify.debug("\nSnapping Photo")
        self.playSound('snap')
        if self.filmCount <= 0:
            self.notify.debug("No Film")
            return


        for rayEntry in self.rayArray:
            posX = (self.viewfinderNode.getX() + (RAYSPREADX * rayEntry[0])) / self.screenSizeX
            posY = (self.viewfinderNode.getZ() + (RAYSPREADY * rayEntry[1])) / self.screenSizeZ
            rayEntry[4].setFromLens(self.lensNode, posX, posY)

        self.traverser.traverse(self.subjectNode)

        distDict = {}
        hitDict = {}
        centerDict = {}

        for i in range(self.queue.getNumEntries()):
            entry = self.queue.getEntry(i)

            object = None
            objectIndex = None
            subjectIndexString= entry.getIntoNodePath().getNetTag('subjectIndex')
            sceneryIndexString= entry.getIntoNodePath().getNetTag('sceneryIndex')
            if subjectIndexString:
                objectIndex = int(subjectIndexString)
                object = self.subjects[objectIndex]
            elif sceneryIndexString:
                objectIndex = int(sceneryIndexString)
                object = self.scenery[objectIndex]

            marker = "g"

            if 'b' in entry.getFromNodePath().getName():
                marker = 'b'
            if 't' in entry.getFromNodePath().getName():
                marker = 't'
            if 'r' in entry.getFromNodePath().getName():
                marker = 'r'
            if 'l' in entry.getFromNodePath().getName():
                marker = 'l'

            if object:
                newEntry = (entry.getFromNode(), object)

                distance = Vec3(entry.getSurfacePoint(self.tripod)).lengthSquared()

                name = entry.getFromNode().getName()
                if not distDict.has_key(name):
                    distDict[name] = distance
                    hitDict[name] = (entry.getFromNode(), object, marker)
                elif distance < distDict[name]:
                    distDict[name] = distance
                    hitDict[name] = (entry.getFromNode(), object, marker)

        for key in hitDict:
            hit = hitDict[key]
            superParent = hit[1]
            marker = hit[2]

            onCenter = 0
            overB = 0
            overT = 0
            overR = 0
            overL = 0
            quality = -1

            if marker == 'b':
                overB = 1
            elif marker == 't':
                overT = 1
            elif marker == 'r':
                overR = 1
            elif marker == 'l':
                overL = 1
            else:
                quality = 1
                onCenter = 1

            if not centerDict.has_key(superParent):
                centerDict[superParent] = (onCenter, overB, overT, overR, overL)
            else:
                centerDict[superParent] = (onCenter + centerDict[superParent][0], overB + centerDict[superParent][1], overT + centerDict[superParent][2], overR + centerDict[superParent][3], overL + centerDict[superParent][4])


        if WANTDOTS:
            for key in self.markerDict:
                node = self.markerDict[key]
                node.setColorScale(Vec4(1,1,1,1))


            for key in hitDict:
                entry = hitDict[key]
                name = entry[0].getName()
                xS = int(name[0:2])
                yS = int(name[3:5])
                node = self.markerDict[(xS, yS)]
                node.setColorScale(Vec4(1.0, 0.0,0.0,1.0))

        centerDictKeys = []
        for key in centerDict:
            centerDictKeys.append(key)

        for subject in centerDictKeys:
            score = self.judgePhoto(subject, centerDict)
            self.notify.debug("Photo is %s / 5 stars" % (score))
            self.notify.debug("assignment compare %s %s" % (self.determinePhotoContent(subject), self.assignments[self.currentAssignment]))
            #if self.determinePhotoContent(subject) == self.assignments[self.currentAssignment]:
            content = self.determinePhotoContent(subject)
            if content:
                photoAnalysisZero = (content[0], content[1])
                if score and (photoAnalysisZero in self.assignments):
                    index = self.assignments.index(photoAnalysisZero)
                    assignment = self.assignments[index]
                    self.notify.debug("assignment complete")
                    if score >= self.assignmentDataDict[assignment][0]:
                        subjectIndex = self.subjects.index(subject)
                        texturePanel =  self.assignmentDataDict[assignment][5]
                        texture = self.assignmentDataDict[assignment][6]
                        buffer = self.assignmentDataDict[assignment][4]
                        panelToon = self.assignmentDataDict[assignment][7]
                        panelToon.hide()
                        buffer.setActive(1)
                        texturePanel.show()
                        texturePanel.setColorScale(1,1,1,1)
                        taskMgr.doMethodLater(0.2, buffer.setActive, "capture Image", [0])
                        if score > self.assignmentDataDict[assignment][0]:
                            self.assignmentDataDict[assignment][0] = score
                            self.updateAssignmentPanels()
                            self.sendUpdate("newClientPhotoScore", [subjectIndex, content[1], score])
                else:
                    self.notify.debug ("assignment not complete")
                    pass

        horzAngle = (self.viewfinderNode.getX() / self.screenSizeX) * 0.5 * base.camLens.getFov()[0]
        vertAngle = (self.viewfinderNode.getZ() / self.screenSizeZ) * 0.5 * base.camLens.getFov()[1]

        horzPointFlat = (self.viewfinderNode.getX() / self.screenSizeX)
        vertPointFlat = (self.viewfinderNode.getZ() / self.screenSizeZ)

        horzLength = base.camLens.getFov()[0] * 0.5
        vertLength = base.camLens.getFov()[1] * 0.5

        horzRadianLength = toRadians(horzLength)
        vertRadianLength = toRadians(vertLength)

        hMRadian = math.atan( horzPointFlat * math.tan(horzRadianLength) )
        vMRadian = math.atan( vertPointFlat * math.tan(vertRadianLength) )

        hMDegree = toDegrees(hMRadian)
        vMDegree = toDegrees(vMRadian)

        self.__decreaseFilmCount()

        if self.filmCount == 0:
            self.sendUpdate("filmOut", [])

        self.notify.debug("Screen angles H:%s V:%s" % (self.swivel.getH(), self.swivel.getP()))
        self.notify.debug("Viewfinder to screen angles H:%s V:%s" % (horzAngle, vertAngle))
        self.notify.debug("Viewfinder to screen angles with math H:%s V:%s" % (hMDegree, vMDegree))


    def newAIPhotoScore(self, playerId, assignmentIndex, score):
        if len(self.assignments) > assignmentIndex:
            assignment = self.assignments[assignmentIndex]
            assignmentData = self.assignmentDataDict[assignment]
            if score > assignmentData[2]:
                assignmentData[2] = score
                assignmentData[3] = playerId
                self.updateAssignmentPanels()

    def determinePhotoContent(self, subject):
        if self.getSubjectTrackState(subject):
            return [subject, self.getSubjectTrackState(subject)[2]]
        else:
            return None

    def judgePhoto(self, subject, centerDict):
        self.notify.debug("judgePhoto")
        self.notify.debug(subject.getName())
        #self.notify.debug(str(self.getSubjectTrackState(subject)))
        self.notify.debug(str(centerDict[subject]))
        a1 = camera.getH(render) % 360
        a2 = subject.getH(render) % 360
        angle = abs(((a1+180-a2)%360)-180)
        self.notify.debug("angle camera:%s subject:%s between:%s" % (camera.getH(render), subject.getH(render), angle))
        self.notify.debug(str(angle))

        centering = centerDict[subject]

        if type(subject) == type(self.subjectToon):
            facing = angle / 180.0
            interest = self.getSubjectTrackState(subject)[3]
            quality = centering[0] - (centering[1] + centering[2] + centering[3] + centering[4])
            tooClose = (centering[1] and centering[2]) or (centering[3] and centering[4])
            portrait = (centering[1] and not (centering[2] or centering[3] or centering[4]))

            self.notify.debug("angle %s facing %s" % (angle, facing))
            self.notify.debug("Interest %s" % (interest))
            self.notify.debug("Quality %s" % (quality))
            self.notify.debug("tooClose %s" % (tooClose))

            if quality <=0:
                return None
            else:
                score = 0
                if angle >=135:
                    score += 2
                elif angle >=90:
                    score += 1
                elif angle <= 60:
                    score -= 1

                score += interest
                if (quality >= 5) and ((not tooClose) or portrait):
                    score += 1
                    if quality >= 10:
                        score +=1
                        if quality >= 15:
                            score +=1
                score -= 2

                if score > NUMSTARS:
                    score = float(NUMSTARS)

                if score <= 0:
                    return 1
                else:

                    return score


        #import pdb; pdb.set_trace()


    def __toggleView(self):
        self.notify.debug("Toggle View")

        hCam = self.swivel.getH()
        vCam = self.swivel.getP()

        horzPointFlat = (self.viewfinderNode.getX() / self.screenSizeX)
        vertPointFlat = (self.viewfinderNode.getZ() / self.screenSizeZ)

        horzLength = base.camLens.getFov()[0] * 0.5
        vertLength = base.camLens.getFov()[1] * 0.5

        horzRadianLength = toRadians(horzLength)
        vertRadianLength = toRadians(vertLength)

        hMRadian = math.atan( horzPointFlat * math.tan(horzRadianLength) )
        vMRadian = math.atan( vertPointFlat * math.tan(vertRadianLength) )

        hMDegree = toDegrees(hMRadian)
        vMDegree = toDegrees(vMRadian)

        if self.zoomedView:
            self.zoomedView = 0
        else:
            self.zoomedView = 1

        if self.zoomedView:
            self.notify.debug("Zoom In")

            hMove = hMDegree * (1.0 - ZOOMRATIO)
            vMove = vMDegree * (1.0 - ZOOMRATIO)
            self.currentFov = self.zoomFov
            base.camLens.setFov(self.zoomFov)
            self.blackoutNode.show()
            self.swivel.setHpr(self.swivel, (hMove * -self.zoomFlip), (vMove * self.zoomFlip), 0)
            #self.swivel.setH(hCam + (hMove * -self.zoomFlip))
            #self.swivel.setP(vCam + (vMove * self.zoomFlip))

        else:
            self.notify.debug("Zoom Out")

            hMove = hMDegree * ((1.0 - ZOOMRATIO) / ZOOMRATIO)
            vMove = vMDegree * ((1.0 - ZOOMRATIO) / ZOOMRATIO)
            self.currentFov = self.outFov
            base.camLens.setFov(self.outFov)
            self.blackoutNode.hide()
            self.swivel.setHpr(self.swivel, (hMove * self.zoomFlip), (vMove * -self.zoomFlip), 0)
            #self.swivel.setH(hCam + (hMove * self.zoomFlip))
            #self.swivel.setP(vCam + (vMove * -self.zoomFlip))


    def __doZoom(self):
        self.notify.debug("Toggle View")

        self.playSound('zoom')

        hCam = self.swivel.getH()
        vCam = self.swivel.getP()

        horzPointFlat = (self.viewfinderNode.getX() / self.screenSizeX)
        vertPointFlat = (self.viewfinderNode.getZ() / self.screenSizeZ)

        horzLength = base.camLens.getFov()[0] * 0.5
        vertLength = base.camLens.getFov()[1] * 0.5

        horzRadianLength = toRadians(horzLength)
        vertRadianLength = toRadians(vertLength)

        hMRadian = math.atan( horzPointFlat * math.tan(horzRadianLength) )
        vMRadian = math.atan( vertPointFlat * math.tan(vertRadianLength) )

        hMDegree = toDegrees(hMRadian)
        vMDegree = toDegrees(vMRadian)

        if self.zoomedView:
            self.zoomedView = 0
        else:
            self.zoomedView = 1

        self.cameraTrack = Sequence()

        if self.zoomedView:
            self.notify.debug("Zoom In")

            hMove = hMDegree * (1.0 - ZOOMRATIO)
            vMove = vMDegree * (1.0 - ZOOMRATIO)
            self.currentFov = self.zoomFov
            base.camLens.setFov(self.zoomFov)
            self.blackoutNode.show()
            #self.swivel.setHpr(self.swivel, (hMove * -self.zoomFlip), (vMove * self.zoomFlip), 0)
            #self.swivel.setH(hCam + (hMove * -self.zoomFlip))
            #self.swivel.setP(vCam + (vMove * self.zoomFlip))

            orgQuat = self.swivel.getQuat()

            self.swivel.setHpr(self.swivel, (hMove * -self.zoomFlip), (vMove * self.zoomFlip), 0)
            self.swivel.setR(0.0)
            newQuat = self.swivel.getQuat()
            self.swivel.setQuat(orgQuat)


            zoomTrack = Parallel()
            zoomTrack.append(LerpQuatInterval(self.swivel, ZOOMTIME, newQuat))
            zoomTrack.append(LerpFunc(base.camLens.setFov, fromData = self.outFov, toData = self.zoomFov, duration = ZOOMTIME))
            zoomTrack.append(LerpFunc(self.setBlackout, fromData = 0.0, toData = 0.5, duration = ZOOMTIME))

            self.cameraTrack.append(zoomTrack)
            self.cameraTrack.append(Func(self.finishZoom, 1))

        else:
            self.notify.debug("Zoom Out")

            hMove = hMDegree * ((1.0 - ZOOMRATIO) / ZOOMRATIO)#* ZOOMRATIO
            vMove = vMDegree * ((1.0 - ZOOMRATIO) / ZOOMRATIO)#* ZOOMRATIO
            self.currentFov = self.outFov
            base.camLens.setFov(self.outFov)
            #self.blackoutNode.hide()
            #self.swivel.setHpr(self.swivel, (hMove * self.zoomFlip), (vMove * -self.zoomFlip), 0)
            #self.swivel.setH(hCam + (hMove * self.zoomFlip))
            #self.swivel.setP(vCam + (vMove * -self.zoomFlip))

            orgQuat = self.swivel.getQuat()

            self.swivel.setHpr(self.swivel, (hMove * self.zoomFlip), (vMove * -self.zoomFlip), 0)
            self.swivel.setR(0.0)
            newQuat = self.swivel.getQuat()
            self.swivel.setQuat(orgQuat)

            zoomTrack = Parallel()
            zoomTrack.append(LerpQuatInterval(self.swivel, ZOOMTIME, newQuat))
            zoomTrack.append(LerpFunc(base.camLens.setFov, fromData = self.zoomFov, toData = self.outFov, duration = ZOOMTIME))
            zoomTrack.append(LerpFunc(self.setBlackout, fromData = 0.5, toData = 0.0, duration = ZOOMTIME))

            self.cameraTrack.append(zoomTrack)
            self.cameraTrack.append(Func(self.blackoutNode.hide))
            self.cameraTrack.append(Func(self.finishZoom, 0))

        self.cameraTrack.start()

    def setBlackout(self, black):
        self.blackoutNode.setColorScale(0.0,0.0,0.0,black)

    def getSubjectTrackState(self, subject):
        subjectTrack = self.subjectTracks.get(subject)
        if subjectTrack:
            interval  = subjectTrack[0]
            timeline = subjectTrack[1]
            time = interval.getT()
            timeCount = time
            timelineIndex = 0
            while timeCount >= 0.0:
                timeCount -= timeline[timelineIndex][1]
                if timeCount >= 0.0:
                    timelineIndex += 1
            return timeline[timelineIndex]
        else:
            return None


    def __setupSubjects(self):
        self.__setupCollisions()
        #self.subjectNode = render.attachNewNode("subjects")
        self.subjects = []
        self.subjectTracks = {}

        self.photoRoot.reparentTo(self.subjectNode)
        self.photoRoot.setTag('sceneryIndex', ("%s" % (len(self.scenery))))
        self.scenery.append(self.photoRoot)

        #scenery = loader.loadModel("phase_4/models/minigames/toon_cannon")
        #scenery.reparentTo(self.subjectNode)
        #scenery.setPos(0,0,2)
        #scenery.setTag('sceneryIndex', ("%s" % (len(self.scenery))))
        #self.scenery.append(scenery)

        random.seed(time.time())
        namegen = NameGenerator.NameGenerator()

        for pathIndex in range(len(self.data["PATHS"])):
            path = self.data["PATHS"][pathIndex]
            subject = Toon.Toon()
            gender = random.choice(['m','f'])
            seed = int(random.random() * 571)
            #subject.setName("%s %s" % (TTLocalizer.ResistanceToonName, self.nameCounter))
            if gender == 'm':
                boy = 1
                girl = 0
            else:
                boy = 0
                girl = 1
            subject.setName(namegen.randomNameMoreinfo(boy = boy, girl = girl)[-1])
            self.nameCounter += 1
            subject.setPickable(0)
            subject.setPlayerType(NametagGroup.CCNonPlayer)
            dna = ToonDNA.ToonDNA()
            dna.newToonRandom(seed, gender, 1)
            #dna.head = "pls"
            subject.setDNAString(dna.makeNetString())
            subject.animFSM.request("neutral")

            subject.setTag('subjectIndex', ("%s" % (len(self.subjects))))
            self.subjects.append(subject)

            height = subject.getHeight()

            self.collSphere = CollisionSphere(0, 0, height*0.5, height*0.5)
            self.collSphere.setTangible(1)
            self.collNode = CollisionNode(self.uniqueName('subject Sphere'))
            self.collNode.setCollideMask(BitMask32.allOn())
            self.collNode.addSolid(self.collSphere)
            self.collNodePath = subject.attachNewNode(self.collNode)


            subject.reparentTo(self.subjectNode)
            subject.setPos(path[0])
            subject.lookAt(path[1])

            subject.show()



            subjectTrack = self.generateToonTrack(subject, path, pathIndex)

            subjectTrack[0].start()

            self.subjectTracks[subject] = subjectTrack

    def regenerateToonTrack(self, subject, path, pathIndex):
        if not hasattr(self, "swivel"):
            return
        subjectTrack = self.generateToonTrack(subject, path, pathIndex)
        subjectTrack[0].start()
        self.subjectTracks[subject] = subjectTrack


    def generateToonTrack(self, subject, path, pathIndex):
        def getNextIndex(curIndex, path):
                return (curIndex + 1) % len(path)
        subjectTrack = Sequence()
        subjectTimeline = []

        timeAccum = 0.0
        pathPointIndex = 0

        orgPos = subject.getPos()
        orgQuat = subject.getQuat()


        while pathPointIndex < len(path):

            nextIndex = getNextIndex(pathPointIndex, path)
            curPoint = path[pathPointIndex]
            nextPoint = path[nextIndex]
            distance = self.slowDistance(curPoint,nextPoint)

            pointTime = distance * 0.25
            subject.setPos(curPoint)
            subject.lookAt(nextPoint)
            nextQuat = subject.getQuat()
            animSetIndex = self.data["PATHANIMREL"][pathIndex]
            animChoice = random.choice(self.data["ANIMATIONS"][animSetIndex])[0]

            #subjectTrack.append(Func(subject.lookAt, nextPoint))

            movetype = random.choice(self.data["MOVEMODES"][animSetIndex])

            turnTime = 0.2

            if movetype[0] == 'swim':
                turnTime = 0.0

            nextInterval = LerpQuatInterval(subject, turnTime, quat = nextQuat)
            subjectTrack.append(nextInterval)
            subjectTimeline.append((timeAccum, nextInterval.getDuration(), "turn", 1.0))
            timeAccum += nextInterval.getDuration()

            #subjectTimeline.append(("Turning", 0.2, ))

            movetype = random.choice(self.data["MOVEMODES"][animSetIndex])

            pointTime = pointTime * movetype[1]

            if movetype[0] == 'swim':
                nextInterval = Sequence()
                startInterval = Func(subject.setP, -60)
                midInterval = Parallel(
                            LerpPosInterval(subject, pointTime ,nextPoint),
                            ActorInterval(subject, movetype[0], loop = 1,duration = pointTime),
                            )
                nextInterval.append(startInterval)
                nextInterval.append(midInterval)

            else:
                nextInterval = Sequence()
                startInterval = Func(subject.setP, 0)
                midInterval = Parallel(
                            LerpPosInterval(subject, pointTime ,nextPoint),
                            ActorInterval(subject, movetype[0], loop = 1,duration = pointTime),
                            )
                nextInterval.append(startInterval)
                nextInterval.append(midInterval)


            subjectTrack.append(nextInterval)
            subjectTimeline.append((timeAccum, nextInterval.getDuration(), movetype[0], 1.0))
            timeAccum += nextInterval.getDuration()

            if animChoice:
                nextInterval = ActorInterval(subject, animChoice, loop = 0)
                subjectTrack.append(nextInterval)
                subjectTimeline.append((timeAccum, nextInterval.getDuration(), animChoice, 2.0))
                timeAccum += nextInterval.getDuration()
            pathPointIndex += 1

        subject.setPos(orgPos)
        subject.setQuat(orgQuat)
        subjectTrack.append(Func(self.regenerateToonTrack, subject,path,pathIndex))

        return (subjectTrack, subjectTimeline)



    def slowDistance(self, point1, point2):
        dx = point1[0] - point2[0]
        dy = point1[1] - point2[1]
        dz = point1[2] - point2[2]
        distance = math.sqrt((dx*dx) + (dy*dy) + (dz*dz))
        return distance


    def getNextPoint(self, pointList, point):
        pointIndex = 0
        length = len(pointList)
        found = 0
        loop = 0
        while (not found) and (loop < length):
            if pointList[index] == point:
                found = 1
            else:
                index += 1
                loop += 1

        if not found:
            return None

        nextPointIndex = loop + 1
        if nextPointIndex >= length:
            nextPointIndex = 0

        return pointList[nextPointIndex]

    def __createTripod(self):
        # create the cannons

        tripod = self.tripodModel.copyTo(hidden)
        swivel = tripod.find("**/cannon")
        self.tripod = tripod
        self.swivel = swivel
        self.pointer = self.swivel.attachNewNode("pointer")
        self.tripod.setPos(self.photoRoot.getPos())
        self.tripod.setPos(self.tripod.getPos() + self.data["TRIPOD_OFFSET"])
        #self.__updatePhotoPosition(avId)


    # generic minigame distributed functions
    def setGameReady(self):
        if not self.hasLocalToon: return
        self.notify.debug("setGameReady")
        if DistributedMinigame.setGameReady(self):
            return

    def setGameStart(self, timestamp):
        if not self.hasLocalToon: return
        self.notify.debug("setGameStart")
        # base class will cause gameFSM to enter initial state
        DistributedMinigame.setGameStart(self, timestamp)

        self.__stopIntro()

        # place the camera behind our cannon
        self.__putCameraOnTripod()

        if not base.config.GetBool('endless-cannon-game', 0):
            # Start counting down the game clock,
            # call __gameTimerExpired when it reaches 0
            self.timer.show()
            self.timer.countdown(self.data["TIME"],
                                 self.__gameTimerExpired)

        self.filmPanel.reparentTo(aspect2d)
        self.scoreMult = MinigameGlobals.getScoreMult(self.cr.playGame.hood.id)

        self.clockStopTime = None

        self.gameFSM.request('aim')
        self.__putCameraOnTripod()
        self.currentAssignment = 0
        assignmentTemplates = self.generateAssignmentTemplates(PhotoGameGlobals.ONSCREENASSIGNMENTS)
        self.generateAssignments(assignmentTemplates)
        self.generateAssignmentPanels()

        self.scorePanel = self.makeScoreFrame()
        self.scorePanel.reparentTo(aspect2d)
        self.scorePanel.setPos(1.05,0.0,-0.725)

        self.updateAssignmentPanels()

        for subject in self.subjects:
            subject.useLOD(1000)

    def setGameExit(self):
        DistributedMinigame.setGameExit(self)
        self.__gameTimerExpired()



    def __gameTimerExpired(self):
        self.notify.debug("game timer expired")
        # finish the game
        self.gameOver()

    def generateAssignments(self, assignmentTemplates):


        for template in assignmentTemplates:
            subject = self.subjects[template[0]]
            pose = template[1]
            score = 0.0
            panel = None
            topScore = 0.0
            topScorerId = None
            textureBuffer = None
            texturePanel = None
            texture = None
            panelToon = None

            assignment = (subject, pose) #score, panel]
            if not (assignment in self.assignments):
                self.assignments.append(assignment)
                self.assignmentDataDict[assignment] = [score, panel, topScore, topScorerId, textureBuffer, texturePanel, texture, panelToon]
        self.notify.debug("assignments")
        for assignment in self.assignments:
            self.notify.debug(str(assignment))
            pass




    def generateAssignmentPanels(self):
        #first remove bad assignments
        self.notify.debug("generateAssignmentPanels")

        for panel in self.assignmentPanels:
            panel.destroy()

        #now generate the panels
        spacing = (self.screenSizeX / PhotoGameGlobals.ONSCREENASSIGNMENTS) * 1.61
        index = 0
        Xoff = self.screenSizeX - 0.735
        Zoff = -self.screenSizeZ + 0.25
        for assignment in self.assignments:

            self.notify.debug("made assignment panel %s" % (str(assignment)))

            panel, texturePanel, toon = self.makeAssignmentPanel(assignment)
            panel.setX(Xoff - (spacing * index))
            panel.setZ(Zoff)
            texturePanel.setZ(0.065)
            rot = random.choice([0.0,2.0,-2.0,-4.0,6.0])
            panel.setR(rot)

            #captureBuffer = base.graphicsEngine.makeBuffer(base.win.getGsg(),'test',0,128,128)
            textureBuffer = base.win.makeTextureBuffer("Photo Capture", 128,128)
            dr = textureBuffer.makeDisplayRegion()
            dr.setCamera(self.captureCam)
            texture = textureBuffer.getTexture()
            texturePanel.setTexture(texture)
            texturePanel.setColorScale(0,0,0,0)
            textureBuffer.setActive(0)
            self.textureBuffers.append(textureBuffer)
            texturePanel.hide()

            self.assignmentPanels.append(panel)
            self.assignmentDataDict[assignment][1] = panel
            self.assignmentDataDict[assignment][4] = textureBuffer
            self.assignmentDataDict[assignment][5] = texturePanel
            self.assignmentDataDict[assignment][6] = texture
            self.assignmentDataDict[assignment][7] = toon
            #assignment[3] = panel
            index += 1

    def printAD(self):
        for assignment in self.assignmentDataDict:
            data = self.assignmentDataDict[assignment]
            print("Key:%s\nData:%s\n" % (str(assignment), data))


    def updateScorePanel(self):
        teamScore = 0.0
        bonusScore = 0.0
        for assignment in self.assignments:
            data = self.assignmentDataDict[assignment]
            teamScore += data[2]
            if data[3] == localAvatar.doId:
                bonusScore += 1.0
        self.scorePanel["text"] = (TTLocalizer.PhotoGameScore % (int(teamScore), int(bonusScore), int(teamScore + bonusScore)))

    def updateAssignmentPanels(self):
        for assignment in self.assignments:
            data = self.assignmentDataDict[assignment]
            leaderName = data[3]
            leader = base.cr.doId2do.get(data[3])
            if not leader:
                data[1]["text"] = " " #(TTLocalizer.PhotoGameScoreBlank % (int(data[0])))
            elif leader.doId == localAvatar.doId:
                data[1]["text"] = (TTLocalizer.PhotoGameScoreYou )
            else:
                leaderName = leader.getName()
                data[1]["text"] = (TTLocalizer.PhotoGameScoreOther % (leaderName))
            starList = self.starDict[data[1]]
            starParent = self.starParentDict[data[1]]
            score = int(data[2])
            for index in range(NUMSTARS):
                if index < score:
                    starList[index].show()
                else:
                    starList[index].hide()
            starParent.setX(float(NUMSTARS - score) * STARSIZE * 0.5)

        self.updateScorePanel()
        #pass



    def makeAssignmentPanel(self, assignment):
        if assignment!= None:
            assignedToon = Toon.Toon()
            assignedToon.setDNA(assignment[0].getStyle())
        else:
            assignedToon = None

        model, ival = self.makeFrameModel(assignedToon)
        if assignedToon:
            assignedToon.loop(assignment[1])

        model.reparentTo(aspect2d)
        assignedToon.setH(172)
        assignedToon.setZ(-1.2)
        assignedToon.setY(100.0)
        if assignment[1] == 'swim':
            assignedToon.setP(-70)
            assignedToon.setH(160)
            assignedToon.setZ(-0.6)

        model.setH(0)
        model.setScale(1.0)
        model["text"] = " "
        assignedToon.setY(-100.0)
        model.setY(-10.0)

        screen = model.attachNewNode("screen node")
        BuildGeometry.addSquareGeom(screen, 0.36, 0.27, Vec4(1.0,1.0,1.0,1.0))
        screen.setHpr(0,90,0)
        screen.setDepthTest(1)
        #screen.setY(-10.5)

        #self.toonList.append(assignedToon)

        starImage = loader.loadModel("phase_4/models/minigames/photogame_star")


        starParent = model.attachNewNode("star parent")

        self.starDict[model] = []
        for index in range(NUMSTARS):
            star = DirectLabel(parent = starParent,
                                image = starImage,
                                image_color = (1,1,1,1),
                                image_scale = Point3(STARSIZE, 0.0, STARSIZE),
                                relief = None,
                                )
            star.setX( (STARSIZE * -0.5 * float(NUMSTARS)) + (float(index + 0.5) * STARSIZE))
            star.setZ(-0.05 - STARSIZE)
            self.starDict[model].append(star)
            self.starParentDict[model] = starParent
            star.hide()

        return model, screen, assignedToon

    def makeFrameModel(self, model):
        # Returns a (DirectWidget, Interval) pair to spin the
        # indicated model, an arbitrary NodePath, on a panel.  Called
        # only on the client, from getPicture(), by derived classes
        # like CatalogFurnitureItem and CatalogClothingItem.

        frame = self.makeAssignmentFrame()
        ival = None
        if model:
            # This 3-d model will be drawn in the 2-d scene.
            model.setDepthTest(1)
            model.setDepthWrite(1)

            # This case is simpler, we do not need all the extra nodes
            scale = frame.attachNewNode('scale')
            model.reparentTo(scale)
            # Translate model to the center.
            bMin,bMax = model.getTightBounds()
            center = (bMin + bMax)/2.0
            model.setPos(-center[0], 2, -center[2])
            corner = Vec3(bMax - center)
            scaleFactor = self.screenSizeX / PhotoGameGlobals.ONSCREENASSIGNMENTS
            #self.what = (0.4 * scaleFactor) /max(corner[0],corner[1],corner[2])
            scale.setScale((0.4 * scaleFactor) /max(corner[0],corner[1],corner[2]))

        return (frame, ival)

    def makeAssignmentFrame(self):
        # Returns a DirectFrame suitable for holding models returned
        # by getPicture().

        # Don't import this at the top of the file, since this code
        # must run on the AI.
        from direct.gui.DirectGui import DirectFrame

        photoImage = loader.loadModel("phase_4/models/minigames/photo_game_pictureframe")

        size = 1.0
        assignmentScale = self.screenSizeX / PhotoGameGlobals.ONSCREENASSIGNMENTS

        frame = DirectFrame(parent = hidden,
                            image = photoImage, # DGG.getDefaultDialogGeom(),
                            image_color = (1,1,1,1),#OTPGlobals.GlobalDialogColor,
                            image_scale = Point3(1.6 * assignmentScale, 0.0, 1.75 * assignmentScale),
                            frameSize = (-size, size, -size, size),
                            text = "HC Score",
                            textMayChange = 1,
                            text_wordwrap = 9,
                            text_pos = Point3(0.0,-0.135,0.0),
                            text_scale = 0.045,
                            relief = None,
                            )

        return frame

    def makeScoreFrame(self):
        # Returns a DirectFrame suitable for holding models returned
        # by getPicture().

        # Don't import this at the top of the file, since this code
        # must run on the AI.
        from direct.gui.DirectGui import DirectFrame

        size = 1.0
        scoreImage = loader.loadModel("phase_4/models/minigames/photogame_camera")
        frame = DirectFrame(parent = hidden,
                            image = scoreImage,
                            image_color = (1,1,1,1),
                            image_scale = Point3(0.64, 0.0, 0.64),
                            frameSize = (-size, size, -size, size),
                            text = "Score Frame",
                            textMayChange = 1,
                            text_wordwrap = 9,
                            text_pos = Point3(0.0,0.0,0.0),
                            text_scale = 0.05,
                            relief = None,
                            )

        return frame

    # ClassicFSM functions
    def enterOff(self):
        self.notify.debug("enterOff")

    def exitOff(self):
        pass

    def enterAim(self):
        self.notify.debug("enterAim")
        self.__enableAimInterface()
        #self.__putCameraOnTripod()
        taskMgr.add(self.__moveViewfinder, "photo game viewfinder Task")
        self.accept('mouse1', self.__handleMouseClick)
        base.localAvatar.laffMeter.stop()
        base.transitions.noIris()



    def exitAim(self):
        self.__disableAimInterface()
        taskMgr.remove("photo game viewfinder Task")
        self.ignore('mouse1')


    def enterZoom(self):
        self.notify.debug("enterZoom")
        taskMgr.add(self.__moveViewfinder, "photo game viewfinder Task")
        #taskMgr.doMethodLater(1.0, self.finishZoom, "finish zoom task")
        self.__doZoom()


    def exitZoom(self):
        taskMgr.remove("photo game viewfinder Task")
        self.notify.debug("exitZoom")

    def finishZoom(self, zoomed = None,task = None):
        if zoomed:
            #for subject in self.subjects:
            #    subject.useLOD(1000)
            self.captureLens.setFov(self.captureZoomFOV)
        else:
            #for subject in self.subjects:
            #    subject.resetLOD()
            self.captureLens.setFov(self.captureOutFOV)
        self.gameFSM.request('aim')
        #self.__toggleView()


    def enterShowResults(self):
        self.notify.debug("enterShowResults")
        # there may still be toons in the air
        # if there are airborne toons, gameOver will be called when they
        # have all landed.
        # otherwise, just call gameOver now
        #if not self.airborneToons:
        #    self.gameOver()

        for subject in self.subjects:
            subject.resetLOD()

    def exitShowResults(self):
        pass

    def enterCleanup(self):
        self.notify.debug("enterCleanup")
        # Stop music
        self.music.stop()

        if hasattr(self, 'jarIval'):
            self.jarIval.finish()
            del self.jarIval

        for avId in self.avIdList:
            # get rid of any tasks that may linger
            taskMgr.remove("firePhoto" + str(avId))
            taskMgr.remove("flyingToon" + str(avId))

    def exitCleanup(self):
        pass

    # UI crep
    def __enableAimInterface(self):

        # listen for key presses
        self.accept(self.FIRE_KEY, self.__fireKeyPressed)
        self.accept(self.UP_KEY, self.__upKeyPressed)
        self.accept(self.DOWN_KEY, self.__downKeyPressed)
        self.accept(self.LEFT_KEY, self.__leftKeyPressed)
        self.accept(self.RIGHT_KEY, self.__rightKeyPressed)

        # start the local cannon move task
        self.__spawnLocalPhotoMoveTask()

    def __disableAimInterface(self):

        self.ignore(self.FIRE_KEY)
        self.ignore(self.UP_KEY)
        self.ignore(self.DOWN_KEY)
        self.ignore(self.LEFT_KEY)
        self.ignore(self.RIGHT_KEY)
        self.ignore(self.FIRE_KEY + "-up")
        self.ignore(self.UP_KEY + "-up")
        self.ignore(self.DOWN_KEY + "-up")
        self.ignore(self.LEFT_KEY + "-up")
        self.ignore(self.RIGHT_KEY + "-up")

        # kill the local cannon move task
        self.__killLocalPhotoMoveTask()

    # keypress handlers
    def __fireKeyPressed(self):
        self.ignore(self.FIRE_KEY)
        self.accept(self.FIRE_KEY+"-up", self.__fireKeyReleased)
        self.__firePressed()

    def __upKeyPressed(self):
        self.ignore(self.UP_KEY)
        self.accept(self.UP_KEY+"-up", self.__upKeyReleased)
        self.__upPressed()

    def __downKeyPressed(self):
        self.ignore(self.DOWN_KEY)
        self.accept(self.DOWN_KEY+"-up", self.__downKeyReleased)
        self.__downPressed()

    def __leftKeyPressed(self):
        self.ignore(self.LEFT_KEY)
        self.accept(self.LEFT_KEY+"-up", self.__leftKeyReleased)
        self.__leftPressed()

    def __rightKeyPressed(self):
        self.ignore(self.RIGHT_KEY)
        self.accept(self.RIGHT_KEY+"-up", self.__rightKeyReleased)
        self.__rightPressed()

    def __fireKeyReleased(self):
        self.ignore(self.FIRE_KEY+"-up")
        self.accept(self.FIRE_KEY, self.__fireKeyPressed)
        self.__fireReleased()

    def __leftKeyReleased(self):
        self.ignore(self.LEFT_KEY+"-up")
        self.accept(self.LEFT_KEY, self.__leftKeyPressed)
        self.__leftReleased()

    def __rightKeyReleased(self):
        self.ignore(self.RIGHT_KEY+"-up")
        self.accept(self.RIGHT_KEY, self.__rightKeyPressed)
        self.__rightReleased()

    def __upKeyReleased(self):
        self.ignore(self.UP_KEY+"-up")
        self.accept(self.UP_KEY, self.__upKeyPressed)
        self.__upReleased()

    def __downKeyReleased(self):
        self.ignore(self.DOWN_KEY+"-up")
        self.accept(self.DOWN_KEY, self.__downKeyPressed)
        self.__downReleased()

    # button event handlers (also used by keyboard event handlers)
    def __firePressed(self):
        self.notify.debug("fire pressed")
        #self.gameFSM.request('shoot')

    def __fireReleased(self):
        #self.__toggleView()
        self.gameFSM.request('zoom')
        pass

    def __upPressed(self):
        self.notify.debug("up pressed")
        self.upPressed = self.__enterControlActive(self.upPressed)

    def __downPressed(self):
        self.notify.debug("down pressed")
        self.downPressed = self.__enterControlActive(self.downPressed)

    def __leftPressed(self):
        self.notify.debug("left pressed")
        self.leftPressed = self.__enterControlActive(self.leftPressed)

    def __rightPressed(self):
        self.notify.debug("right pressed")
        self.rightPressed = self.__enterControlActive(self.rightPressed)

    def __upReleased(self):
        self.notify.debug("up released")
        self.upPressed = self.__exitControlActive(self.upPressed)

    def __downReleased(self):
        self.notify.debug("down released")
        self.downPressed = self.__exitControlActive(self.downPressed)

    def __leftReleased(self):
        self.notify.debug("left released")
        self.leftPressed = self.__exitControlActive(self.leftPressed)

    def __rightReleased(self):
        self.notify.debug("right released")
        self.rightPressed = self.__exitControlActive(self.rightPressed)

    def __handleMouseClick(self):
        self.notify.debug("mouse click")
        self.__testCollisions()


    # __enterControlActive and __exitControlActive are used
    # to update the cannon control 'press reference counts'
    # leftPressed, rightPressed, upPressed, and downPressed
    # are all counts of how many devices (button, keys) are
    # activating that particular cannon control -- so if
    # someone is pressing 'right' on the keyboard and also
    # pressing on the 'right' button with the mouse,
    # rightPressed would be set to 2. A value of zero means
    # that the cannon control is inactive.
    def __enterControlActive(self, control):
        return control + 1

    def __exitControlActive(self, control):
        return max(0, control-1)


    def __spawnLocalPhotoMoveTask(self):
        self.leftPressed = 0
        self.rightPressed = 0
        self.upPressed = 0
        self.downPressed = 0

        self.photoMoving = 0

        task = Task(self.__localPhotoMoveTask)
        task.lastPositionBroadcastTime = 0.
        taskMgr.add(task, self.LOCAL_PHOTO_MOVE_TASK)

    def __killLocalPhotoMoveTask(self):
        taskMgr.remove(self.LOCAL_PHOTO_MOVE_TASK)
        if self.photoMoving:
            self.sndPhotoMove.stop()

    def __localPhotoMoveTask(self, task):
        """ this task moves the cannon
        """
        if not hasattr(self, "swivel"):
            return

        pos = [self.swivel.getHpr()[0],self.swivel.getHpr()[1],self.swivel.getHpr()[2]]

        # these are used to determine if the cannon actually moved
        oldRot = pos[0]
        oldAng = pos[1]

        # cannon rotation
        rotVel = 0
        if self.leftPressed:
            rotVel += PhotoGameGlobals.PHOTO_ROTATION_VEL
        if self.rightPressed:
            rotVel -= PhotoGameGlobals.PHOTO_ROTATION_VEL
        pos[0] += rotVel * globalClock.getDt()

        # cannon barrel angle
        angVel = 0
        if self.upPressed:
            angVel += PhotoGameGlobals.PHOTO_ANGLE_VEL
        if self.downPressed:
            angVel -= PhotoGameGlobals.PHOTO_ANGLE_VEL
        pos[1] += angVel * globalClock.getDt()
        if pos[1] < PhotoGameGlobals.PHOTO_ANGLE_MIN:
            pos[1] = PhotoGameGlobals.PHOTO_ANGLE_MIN
        elif pos[1] > PhotoGameGlobals.PHOTO_ANGLE_MAX:
            pos[1] = PhotoGameGlobals.PHOTO_ANGLE_MAX

        if oldRot != pos[0] or oldAng != pos[1]:
            if self.photoMoving == 0:
                self.photoMoving = 1
                base.playSfx(self.sndPhotoMove, looping=1)

            #self.__updatePhotoPosition(self.localAvId)
            posVec = Vec3(pos[0], pos[1], pos[2])

            self.swivel.setHpr(posVec)

        else:
            if self.photoMoving:
                self.photoMoving = 0
                self.sndPhotoMove.stop()

        return Task.cont



    def __putCameraOnTripod(self):
        camera.setPosHpr(0,0.0,0,0,0,0)
        camera.reparentTo(self.swivel)
        self.swivel.setHpr(self.data["START_HPR"])


    def __loadToonInTripod(self, avId):
        toon = base.cr.doId2do.get(avId)
        if toon:
            toon.reparentTo(self.swivel)


    def __toRadians(self, angle):
        return angle * 2.0 * math.pi / 360.0

    def __toDegrees(self, angle):
        return angle * 360.0 / (2.0 * math.pi)



    def __decreaseFilmCount(self):
        curTime = self.getCurrentGameTime()

        # if this is the first time through, init the task's
        # record of the score
        score = self.filmCount - 1
        if not hasattr(self, 'curScore'):
            self.curScore = score

        self.filmPanel['text'] = str(score)

        if self.curScore != score:
            if hasattr(self, 'jarIval'):
                self.jarIval.finish()

            # make the jar animate
            s = self.filmPanel.getScale()
            self.jarIval = Parallel(\
                Sequence(self.filmPanel.scaleInterval(.15, s*3./4.,
                                                        blendType='easeOut'),
                         self.filmPanel.scaleInterval(.15, s,
                                                        blendType='easeIn'),
                         ),
                Sequence(
                    Wait(0.25),
                    SoundInterval(self.sndFilmTick),
                    ),
                name='photoGameFilmJarThrob')
            self.jarIval.start()

        self.curScore = score
        self.filmCount = score


    #######################################################################
    # intro fly-by stuff
    #######################################################################

    def __stopIntro(self):
        taskMgr.remove(self.INTRO_TASK_NAME)
        taskMgr.remove(self.INTRO_TASK_NAME_CAMERA_LERP)

        self.__putCameraOnTripod()

        if self.introSequence:
            self.introSequence.finish()
            self.introSequence = None

    def __startIntro(self):

        camera.reparentTo(render)
        camera.setPos(self.data["CAMERA_INTIAL_POSTION"])
        camera.setHpr(0,0,0)

        camera.lookAt(self.tripod)

        lookatHpr = camera.getHpr()

        #camera.setHpr(0,0,0)

        self.introSequence = LerpPosHprInterval(camera, 4.0,
                                                pos = self.tripod.getPos(render),
                                                hpr = lookatHpr,
                                                startPos = self.data["CAMERA_INTIAL_POSTION"],
                                                blendType = 'easeInOut',)
                                                #startHpr = Point3(0,0,0))
        self.introSequence.start()



####AREA SPECIFIC ROUTINES

    def construct(self):
        zone = self.getSafezoneId()
        if zone == ToontownGlobals.ToontownCentral:
            self.constructTTC()
        elif zone == ToontownGlobals.DonaldsDock:
            self.constructDD()
        elif zone == ToontownGlobals.DaisyGardens:
            self.constructDG()
        elif zone == ToontownGlobals.MinniesMelodyland:
            self.constructMM()
        elif zone == ToontownGlobals.TheBrrrgh:
            self.constructBR()
        elif zone == ToontownGlobals.DonaldsDreamland:
            self.constructDL()


    def destruct(self):
        zone = self.getSafezoneId()
        if zone == ToontownGlobals.ToontownCentral:
            self.destructTTC()
        elif zone == ToontownGlobals.DonaldsDock:
            self.destructDD()
        elif zone == ToontownGlobals.DaisyGardens:
            self.destructDG()
        elif zone == ToontownGlobals.MinniesMelodyland:
            self.destructMM()
        elif zone == ToontownGlobals.TheBrrrgh:
            self.destructBR()
        elif zone == ToontownGlobals.DonaldsDreamland:
            self.destructDL()


    def constructTTC(self):
        self.photoRoot = self.scene.find("**/prop_gazebo*")
        self.sky = loader.loadModel("phase_3.5/models/props/TT_sky")
        self.sky.reparentTo(render)
        self.sky.setBin("background", -100)
        self.sky.find("**/cloud1").setBin("background", -99)
        self.sky.find("**/cloud2").setBin("background", -98)
        self.scene.reparentTo(render)
        self.makeDictionaries(self.dnaStore)
        self.createAnimatedProps(self.nodeList)
        self.startAnimatedProps()
        self.scene.find("**/door_trigger_22*").hide()
        self.scene.find("**/doorFrameHoleRight_0*").hide()
        self.scene.find("**/doorFrameHoleLeft_0*").hide()

    def destructTTC(self):
        self.stopAnimatedProps()
        self.deleteAnimatedProps()
        pass

    def constructDD(self):
        self.photoRoot = self.scene.find("**/center_island*")
        self.sky = loader.loadModel("phase_3.5/models/props/BR_sky")
        self.sky.reparentTo(render)
        self.sky.setBin("background", -100)
        self.sky.find("**/skypanel1").setBin("background", -98)
        self.sky.find("**/skypanel2").setBin("background", -97)
        self.sky.find("**/skypanel3").setBin("background", -96)
        self.sky.find("**/skypanel4").setBin("background", -95)
        self.sky.find("**/skypanel5").setBin("background", -94)
        self.sky.find("**/skypanel6").setBin("background", -93)
        self.scene.reparentTo(render)
        self.makeDictionaries(self.dnaStore)
        self.createAnimatedProps(self.nodeList)
        self.startAnimatedProps()
        boatGeom = self.scene.find('**/donalds_boat')
        self.photoRoot.setPos(-22,0,0)

        self.boat = self.photoRoot.attachNewNode("boat")
        boatGeom.reparentTo(self.boat)
        boatGeom.setX(45.0)
        boatGeom.setY(-5.0)
        boatGeom.setR(-0.0)
        boatGeom.setH(-8)
        self.bg = boatGeom
        self.boatTrack = Sequence()
        self.boatTrack.append(LerpHprInterval(self.boat, 90.0, Point3(360,0,0)))
        self.boatTrack.loop()
        self.boatTrack2 = Sequence()
        self.boatTrack2.append(LerpPosInterval(self.boat, 5.0, Point3(0,0,2.0), Point3(0,0,1.0), blendType = 'easeInOut'))
        self.boatTrack2.append(LerpPosInterval(self.boat, 5.0, Point3(0,0,1.0), Point3(0,0,2.0), blendType = 'easeInOut'))
        self.boatTrack2.loop()
        ddFog = Fog("DDFog Photo")
        ddFog.setColor(Vec4(0.8, 0.8, 0.8, 1.0))
        ddFog.setLinearRange(0.0, 400.0)
        render.setFog(ddFog)

        water = self.scene.find("**/top_surface")
        water.setTransparency(TransparencyAttrib.MAlpha)
        water.setColorScale(1.0,1.0,1.0,0.8)
        water.setDepthWrite(1)
        water.setDepthTest(1)
        water.setBin('transparent', 0)


    def destructDD(self):
        self.bg = None
        self.boatTrack.finish()
        self.boatTrack2.finish()
        self.boat.removeNode()
        render.clearFog()
        self.stopAnimatedProps()
        self.deleteAnimatedProps()
        pass

    def constructDG(self):
        self.photoRoot = render.attachNewNode("DG PhotoRoot")
        self.photoRoot.setPos(1.39, 92.91, 2.0)
        self.bigFlower = loader.loadModel('phase_8/models/props/DG_flower-mod.bam')
        self.bigFlower.reparentTo(self.photoRoot)
        self.bigFlower.setScale(2.5)
        self.sky = loader.loadModel("phase_3.5/models/props/TT_sky")
        self.sky.reparentTo(render)
        self.sky.setBin("background", -100)
        self.sky.find("**/cloud1").setBin("background", -99)
        self.sky.find("**/cloud2").setBin("background", -98)
        self.scene.reparentTo(render)

        self.scene.find("**/door_trigger_5*").hide()
        self.scene.find("**/doorFrameHoleRight_0*").hide()
        self.scene.find("**/doorFrameHoleLeft_0*").hide()

        #maze = self.scene.find("**/hedges*")
        for name in ["**/o10_2"]:
            maze = self.scene.find(name)
            maze.reparentTo(self.subjectNode)
            maze.setTag('sceneryIndex', ("%s" % (len(self.scenery))))
            self.scenery.append(maze)


        self.makeDictionaries(self.dnaStore)
        self.createAnimatedProps(self.nodeList)
        self.startAnimatedProps()


    def destructDG(self):
        self.bigFlower.removeNode()
        self.stopAnimatedProps()
        self.deleteAnimatedProps()
        pass

    def constructMM(self):
        self.photoRoot = render.attachNewNode("MM PhotoRoot")
        self.photoRoot.setPos(103.6, -61, -4.497)
        self.sky = loader.loadModel("phase_6/models/props/MM_sky")
        self.sky.reparentTo(render)
        self.sky.setBin("background", -100)
        #self.sky.find("**/cloud1").setBin("background", -99)
        #self.sky.find("**/cloud2").setBin("background", -98)
        self.scene.reparentTo(render)

        self.scene.find("**/door_trigger_8*").hide()
        self.scene.find("**/door_trigger_6*").hide()
        self.scene.find("**/door_trigger_1*").hide()
        self.scene.find("**/door_trigger_0*").hide()
        self.scene.find("**/door_trigger_3*").hide()
        self.scene.find("**/doorFrameHoleRight_0*").hide()
        self.scene.find("**/doorFrameHoleLeft_0*").hide()
        self.scene.find("**/doorFrameHoleRight_1*").hide()
        self.scene.find("**/doorFrameHoleLeft_1*").hide()
        self.scene.find("**/doorFrameHoleRight").hide()
        self.scene.find("**/doorFrameHoleLeft").hide()

        self.makeDictionaries(self.dnaStore)
        self.createAnimatedProps(self.nodeList)
        self.startAnimatedProps()

        lm = self.scene.findAllMatches("**/*landmark*")

        blocker = lm[2]
        blocker.reparentTo(self.subjectNode)
        blocker.setTag('sceneryIndex', ("%s" % (len(self.scenery))))
        self.scenery.append(blocker)

        #for name in ["**/toon_landmark_hqMM_DNARoot"]:
        #    blocker = self.scene.find(name)
        #    blocker.reparentTo(self.subjectNode)
        #    blocker.setTag('sceneryIndex', ("%s" % (len(self.scenery))))
        #    self.scenery.append(blocker)


    def destructMM(self):
        self.stopAnimatedProps()
        self.deleteAnimatedProps()
        pass

    def constructBR(self):
        self.photoRoot = render.attachNewNode("BR PhotoRoot")
        self.photoRoot.setPos(-110, -48, 8.567)
        self.sky = loader.loadModel("phase_3.5/models/props/BR_sky")
        self.sky.reparentTo(render)
        self.sky.setBin("background", -100)
        #self.sky.find("**/cloud1").setBin("background", -99)
        #self.sky.find("**/cloud2").setBin("background", -98)
        self.scene.reparentTo(render)

        self.scene.find("**/door_trigger_11*").hide()
        self.scene.find("**/doorFrameHoleRight_0*").hide()
        self.scene.find("**/doorFrameHoleLeft_0*").hide()

        self.makeDictionaries(self.dnaStore)
        self.createAnimatedProps(self.nodeList)
        self.startAnimatedProps()

        self.snow = BattleParticles.loadParticleFile('snowdisk.ptf')
        self.snow.setPos(0, 0, 5)  # start the snow slightly above the camera
        self.snowRender = self.scene.attachNewNode('snowRender')
        self.snowRender.setDepthWrite(0)
        self.snowRender.setBin('fixed', 1)
        self.snowFade = None
        self.snow.start(camera, self.snowRender)


    def destructBR(self):
        self.snow.cleanup()
        del self.snow
        del self.snowRender
        self.stopAnimatedProps()
        self.deleteAnimatedProps()
        pass


    def constructDL(self):
        self.photoRoot = render.attachNewNode("DL PhotoRoot")
        self.photoRoot.setPos(-70.228,  87.588,  4.397)
        self.sky = loader.loadModel("phase_8/models/props/DL_sky")
        self.sky.reparentTo(render)
        self.sky.setBin("background", -100)
        #self.sky.find("**/cloud1").setBin("background", -99)
        #self.sky.find("**/cloud2").setBin("background", -98)
        self.scene.reparentTo(render)

        self.scene.find("**/door_trigger_8*").hide()
        self.scene.find("**/doorFrameHoleRight_0*").hide()
        self.scene.find("**/doorFrameHoleLeft_0*").hide()
        self.scene.find("**/doorFrameHoleRight_1*").hide()
        self.scene.find("**/doorFrameHoleLeft_1*").hide()

        self.makeDictionaries(self.dnaStore)
        self.createAnimatedProps(self.nodeList)
        self.startAnimatedProps()


    def destructDL(self):
        self.stopAnimatedProps()
        self.deleteAnimatedProps()
        pass

    def makeDictionaries(self, dnaStore):
        assert(self.notify.debug("makeDictionaries()"))
        # A list of all visible nodes
        self.nodeList = []
        # There should only be one vis group
        for i in range(dnaStore.getNumDNAVisGroups()):
            groupFullName = dnaStore.getDNAVisGroupName(i)
            groupName = base.cr.hoodMgr.extractGroupName(groupFullName)
            groupNode = self.scene.find("**/" + groupFullName)
            if groupNode.isEmpty():
                self.notify.error("Could not find visgroup")
            self.nodeList.append(groupNode)

    def startAnimatedProps(self):
        for animPropListKey in self.animPropDict:
            animPropList = self.animPropDict[animPropListKey]
            for animProp in animPropList:
                animProp.enter()

    def stopAnimatedProps(self):
        for animPropListKey in self.animPropDict:
            animPropList = self.animPropDict[animPropListKey]
            for animProp in animPropList:
                animProp.exit()

    def createAnimatedProps(self, nodeList):
        assert(self.notify.debug("createAnimatedProps()"))
        self.animPropDict = {}
        for i in nodeList:
            # Get all the anim in the vis group
            animPropNodes = i.findAllMatches("**/animated_prop_*")
            numAnimPropNodes = animPropNodes.getNumPaths()
            for j in range(numAnimPropNodes):
                animPropNode = animPropNodes.getPath(j)

                if animPropNode.getName().startswith('animated_prop_generic'):
                    className = 'GenericAnimatedProp'
                else:
                    # The node name should be "animated_prop_ClassName_DNARoot"
                    # So strip off the first and last junk to get the ClassName
                    className = animPropNode.getName()[14:-8]

                symbols = {}
                base.cr.importModule(symbols, 'toontown.hood', [className])

                classObj = getattr(symbols[className], className)
                animPropObj = classObj(animPropNode)
                animPropList = self.animPropDict.setdefault(i, [])
                animPropList.append(animPropObj)

            interactivePropNodes = i.findAllMatches("**/interactive_prop_*")
            numInteractivePropNodes = interactivePropNodes.getNumPaths()
            for j in range(numInteractivePropNodes):
                interactivePropNode = interactivePropNodes.getPath(j)
                className = 'GenericAnimatedProp'

                symbols = {}
                base.cr.importModule(symbols, 'toontown.hood', [className])

                classObj = getattr(symbols[className], className)
                interactivePropObj = classObj(interactivePropNode)
                # [gjeon] I think we can use animPropList to store interactive props
                animPropList = self.animPropDict.get(i)
                if animPropList is None:
                    animPropList = self.animPropDict.setdefault(i, [])
                animPropList.append(interactivePropObj)

    def deleteAnimatedProps(self):
        for animPropListKey in self.animPropDict:
            animPropList = self.animPropDict[animPropListKey]
            for animProp in animPropList:
                animProp.delete()
        del self.animPropDict


    def addSound(self, name, soundName, path = None):
        if not hasattr(self, "soundTable"):
            self.soundTable = {}
        if path:
            self.soundPath = path
        soundSource = ("%s%s" % (self.soundPath, soundName))
        self.soundTable[name] = loader.loadSfx(soundSource)

    def playSound(self, name, volume = 1.0):
        if hasattr(self, 'soundTable'):
            self.soundTable[name].setVolume(volume)
            self.soundTable[name].play()
