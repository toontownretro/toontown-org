
from pandac.PandaModules import *
import ToonHood
from toontown.safezone import OZSafeZoneLoader
from toontown.toonbase.ToontownGlobals import *
from toontown.racing import DistributedVehicle
import SkyUtil

class OZHood(ToonHood.ToonHood):
    def __init__(self, parentFSM, doneEvent, dnaStore, hoodId):
        ToonHood.ToonHood.__init__(self, parentFSM, doneEvent, dnaStore,
                                   hoodId)
        self.id = OutdoorZone
        # Create the safe zone state data
        #self.storageDNAFile = None
        self.safeZoneLoaderClass = OZSafeZoneLoader.OZSafeZoneLoader
        self.storageDNAFile = "phase_6/dna/storage_OZ.dna"

        # Dictionary which holds holiday specific lists of Storage DNA Files
        # Keyed off of the News Manager holiday IDs stored in ToontownGlobals
        self.holidayStorageDNADict = {HALLOWEEN_PROPS : ['phase_6/dna/halloween_props_storage_OZ.dna'],
                                      SPOOKY_PROPS: ['phase_6/dna/halloween_props_storage_OZ.dna']}
        self.skyFile = "phase_3.5/models/props/TT_sky"
        self.spookySkyFile = "phase_3.5/models/props/BR_sky"
        self.titleColor = (1.0, 0.5, 0.4, 1.0)
        self.whiteFogColor = Vec4(.95, 0.95, 0.95, 1)
        self.underwaterFogColor = Vec4(0.0, 0.0, 0.6, 1.0)

    def load(self):
        ToonHood.ToonHood.load(self)
        self.parentFSM.getStateNamed("OZHood").addChild(self.fsm)
        self.fog = Fog("OZFog")

    def unload(self):
        self.parentFSM.getStateNamed("OZHood").removeChild(self.fsm)
        ToonHood.ToonHood.unload(self)

    def enter(self, *args):
        ToonHood.ToonHood.enter(self, *args)
        base.camLens.setNearFar(SpeedwayCameraNear,
                                SpeedwayCameraFar)


    def exit(self):
        base.camLens.setNearFar(DefaultCameraNear,
                                DefaultCameraFar)
        ToonHood.ToonHood.exit(self)

    def skyTrack(self, task):
        return SkyUtil.cloudSkyTrack(task)

    def startSky(self):

        # we have the wrong sky; load in the regular sky
        if not (self.sky.getTag("sky") == "Regular"):
            self.endSpookySky()

        SkyUtil.startCloudSky(self)

    def setUnderwaterFog(self):
        if base.wantFog:
            self.fog.setColor(self.underwaterFogColor)
            self.fog.setLinearRange(0.1, 100.0)
            render.setFog(self.fog)
            self.sky.setFog(self.fog)

    def setWhiteFog(self):
        if base.wantFog:
            self.fog.setColor(self.whiteFogColor)
            self.fog.setLinearRange(0.0, 400.0)
            render.clearFog()
            render.setFog(self.fog)
            # Insist that fog is on the sky.  This will prevent the
            # sky from being contaminated by the trolley tunnel shadow
            # if we jump on the trolley.
            self.sky.clearFog()
            self.sky.setFog(self.fog)

    def setNoFog(self):
        if base.wantFog:
            render.clearFog()
            self.sky.clearFog()

    def startSpookySky(self):
        if self.sky:
            self.stopSky()
        self.sky = loader.loadModel(self.spookySkyFile)
        self.sky.setTag("sky", "Halloween")
        self.sky.setScale(1.0)
        self.sky.setDepthTest(0)
        self.sky.setDepthWrite(0)
        self.sky.setColor(0.5,0.5,0.5,1)
        self.sky.setBin("background", 100)
        self.sky.setFogOff()
        self.sky.reparentTo(camera)

        #fade the sky in
        self.sky.setTransparency(TransparencyAttrib.MDual, 1)
        fadeIn = self.sky.colorScaleInterval( 1.5, Vec4(1, 1, 1, 1),
                                               startColorScale = Vec4(1, 1, 1, 0.25),
                                               blendType = 'easeInOut')
        fadeIn.start()

        # Nowadays we use a CompassEffect to counter-rotate the sky
        # automatically at render time, rather than depending on a
        # task to do this just before the scene is rendered.
        self.sky.setZ(0.0)
        self.sky.setHpr(0.0, 0.0, 0.0)
        ce = CompassEffect.make(NodePath(), CompassEffect.PRot | CompassEffect.PZ)
        self.sky.node().setEffect(ce)
