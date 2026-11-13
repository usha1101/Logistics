import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'

interface MovingVehicle {
  group: THREE.Group
  bodyGroup: THREE.Group
  wheels: THREE.Group[]
  laneZSpeed: number
  wheelRadius: number
  phaseOffset: number
}

const CORRIDOR_ANGLE = 0.56
const TRACK_MIN_Z = -72
const TRACK_MAX_Z = 72
const TRACK_SPAN = TRACK_MAX_Z - TRACK_MIN_Z

function buildSemiTruck(
  materials: {
    cabPaint: THREE.Material
    cabTrim: THREE.Material
    glass: THREE.Material
    trailer: THREE.Material
    trailerPanel: THREE.Material
    limeAccent: THREE.Material
    chassis: THREE.Material
    tire: THREE.Material
    rim: THREE.Material
    headlight: THREE.Material
    taillight: THREE.Material
    beam: THREE.Material
  },
  scale = 0.78,
): { group: THREE.Group; bodyGroup: THREE.Group; wheels: THREE.Group[] } {
  const group = new THREE.Group()
  const bodyGroup = new THREE.Group()
  const wheels: THREE.Group[] = []

  // Chassis spine connecting tractor and trailer
  const spine = new THREE.Mesh(new THREE.BoxGeometry(0.95, 0.22, 9.6), materials.chassis)
  spine.position.set(0, 0.62, -0.75)
  spine.castShadow = true
  bodyGroup.add(spine)

  // Tractor cab (+Z is forward)
  const cab = new THREE.Mesh(new THREE.BoxGeometry(1.94, 2.05, 2.25), materials.cabPaint)
  cab.position.set(0, 1.72, 2.68)
  cab.castShadow = true
  cab.receiveShadow = true
  bodyGroup.add(cab)

  // Forward aerodynamic hood
  const hood = new THREE.Mesh(new THREE.BoxGeometry(1.82, 1.28, 1.05), materials.cabPaint)
  hood.position.set(0, 1.33, 4.18)
  hood.castShadow = true
  bodyGroup.add(hood)

  // Aerodynamic roof fairing
  const fairing = new THREE.Mesh(new THREE.BoxGeometry(1.88, 0.62, 1.75), materials.cabPaint)
  fairing.position.set(0, 3.02, 2.48)
  fairing.rotation.x = 0.14
  fairing.castShadow = true
  bodyGroup.add(fairing)

  // Reflective windshield & side windows
  const windshield = new THREE.Mesh(new THREE.BoxGeometry(1.7, 0.78, 0.12), materials.glass)
  windshield.position.set(0, 2.24, 3.82)
  windshield.rotation.x = -0.18
  bodyGroup.add(windshield)

  const sideWinGeo = new THREE.BoxGeometry(0.06, 0.64, 1.08)
  for (const side of [-1, 1]) {
    const win = new THREE.Mesh(sideWinGeo, materials.glass)
    win.position.set(side * 0.96, 2.2, 2.95)
    bodyGroup.add(win)
  }

  // Front grille & bumper
  const grille = new THREE.Mesh(new THREE.BoxGeometry(1.28, 0.72, 0.12), materials.cabTrim)
  grille.position.set(0, 1.24, 4.71)
  bodyGroup.add(grille)

  const bumper = new THREE.Mesh(new THREE.BoxGeometry(1.98, 0.42, 0.34), materials.cabTrim)
  bumper.position.set(0, 0.78, 4.66)
  bumper.castShadow = true
  bodyGroup.add(bumper)

  // Autonomous LiDAR dome + Cyber-Lime sensor ring on cab roof
  const lidarPod = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.22, 0.16, 16), materials.chassis)
  lidarPod.position.set(0, 3.38, 2.85)
  bodyGroup.add(lidarPod)

  const lidarRing = new THREE.Mesh(new THREE.TorusGeometry(0.21, 0.028, 8, 24), materials.limeAccent)
  lidarRing.rotation.x = Math.PI / 2
  lidarRing.position.set(0, 3.39, 2.85)
  bodyGroup.add(lidarRing)

  // Cab side cyber-lime stripe
  const cabStripe = new THREE.Mesh(new THREE.BoxGeometry(1.97, 0.07, 2.1), materials.limeAccent)
  cabStripe.position.set(0, 1.15, 2.68)
  bodyGroup.add(cabStripe)

  // Headlights + forward ground beam projection (zero extra SpotLight GPU cost)
  const hlGeo = new THREE.BoxGeometry(0.36, 0.14, 0.08)
  const beamGeo = new THREE.PlaneGeometry(1.6, 5.2)
  for (const side of [-1, 1]) {
    const hl = new THREE.Mesh(hlGeo, materials.headlight)
    hl.position.set(side * 0.68, 0.95, 4.74)
    bodyGroup.add(hl)

    const beam = new THREE.Mesh(beamGeo, materials.beam)
    beam.rotation.x = -Math.PI / 2
    beam.position.set(side * 0.68, 0.03, 7.25)
    group.add(beam)
  }

  // Articulated Freight Trailer
  const trailer = new THREE.Mesh(new THREE.BoxGeometry(2.14, 2.75, 6.95), materials.trailer)
  trailer.position.set(0, 2.15, -2.55)
  trailer.castShadow = true
  trailer.receiveShadow = true
  bodyGroup.add(trailer)

  // Subtle architectural panel ribs on trailer sides for crisp silhouette depth
  for (const offsetZ of [-4.9, -3.3, -1.7, -0.1]) {
    const rib = new THREE.Mesh(new THREE.BoxGeometry(2.17, 2.45, 0.08), materials.trailerPanel)
    rib.position.set(0, 2.15, offsetZ)
    bodyGroup.add(rib)
  }

  // Trailer aerodynamic side skirts
  const skirt = new THREE.Mesh(new THREE.BoxGeometry(2.1, 0.56, 4.4), materials.chassis)
  skirt.position.set(0, 0.78, -2.1)
  bodyGroup.add(skirt)

  // Cyber-lime LogiPulse livery stripe on trailer
  const trStripe = new THREE.Mesh(new THREE.BoxGeometry(2.19, 0.16, 6.2), materials.limeAccent)
  trStripe.position.set(0, 2.24, -2.55)
  bodyGroup.add(trStripe)

  // Rear red LED taillights
  const tlGeo = new THREE.BoxGeometry(0.42, 0.12, 0.06)
  for (const side of [-1, 1]) {
    const tl = new THREE.Mesh(tlGeo, materials.taillight)
    tl.position.set(side * 0.78, 0.88, -6.04)
    bodyGroup.add(tl)
  }

  group.add(bodyGroup)

  // Wheel builder (wheelGroup centered at y = 0.48 so bottom touches asphalt y = 0)
  const wheelRadius = 0.48
  const tireGeo = new THREE.CylinderGeometry(wheelRadius, wheelRadius, 0.36, 20)
  const rimGeo = new THREE.CylinderGeometry(0.28, 0.28, 0.38, 14)

  const addAxle = (zPos: number, halfTrack: number) => {
    for (const side of [-1, 1]) {
      const wg = new THREE.Group()
      wg.position.set(side * halfTrack, wheelRadius, zPos)

      const tire = new THREE.Mesh(tireGeo, materials.tire)
      tire.rotation.z = Math.PI / 2
      tire.castShadow = true
      wg.add(tire)

      const rim = new THREE.Mesh(rimGeo, materials.rim)
      rim.rotation.z = Math.PI / 2
      wg.add(rim)

      group.add(wg)
      wheels.push(wg)
    }
  }

  addAxle(3.85, 0.96) // Steer front
  addAxle(1.85, 0.98) // Tractor drive
  addAxle(-4.35, 1.02) // Trailer tandem 1
  addAxle(-5.45, 1.02) // Trailer tandem 2

  group.scale.setScalar(scale)
  return { group, bodyGroup, wheels }
}

function buildDeliveryVan(
  materials: {
    cabPaint: THREE.Material
    glass: THREE.Material
    trailer: THREE.Material
    limeAccent: THREE.Material
    chassis: THREE.Material
    tire: THREE.Material
    rim: THREE.Material
    headlight: THREE.Material
    taillight: THREE.Material
    beam: THREE.Material
  },
  scale = 0.78,
): { group: THREE.Group; bodyGroup: THREE.Group; wheels: THREE.Group[] } {
  const group = new THREE.Group()
  const bodyGroup = new THREE.Group()
  const wheels: THREE.Group[] = []

  const chassis = new THREE.Mesh(new THREE.BoxGeometry(1.7, 0.25, 5.1), materials.chassis)
  chassis.position.set(0, 0.5, 0)
  bodyGroup.add(chassis)

  const cargoBox = new THREE.Mesh(new THREE.BoxGeometry(1.85, 2.05, 3.6), materials.trailer)
  cargoBox.position.set(0, 1.62, -0.75)
  cargoBox.castShadow = true
  cargoBox.receiveShadow = true
  bodyGroup.add(cargoBox)

  const stripe = new THREE.Mesh(new THREE.BoxGeometry(1.89, 0.14, 3.2), materials.limeAccent)
  stripe.position.set(0, 1.7, -0.75)
  bodyGroup.add(stripe)

  const cab = new THREE.Mesh(new THREE.BoxGeometry(1.76, 1.55, 1.55), materials.cabPaint)
  cab.position.set(0, 1.32, 1.75)
  cab.castShadow = true
  bodyGroup.add(cab)

  const windshield = new THREE.Mesh(new THREE.BoxGeometry(1.58, 0.68, 0.1), materials.glass)
  windshield.position.set(0, 1.65, 2.52)
  windshield.rotation.x = -0.2
  bodyGroup.add(windshield)

  const lidar = new THREE.Mesh(new THREE.TorusGeometry(0.16, 0.025, 8, 20), materials.limeAccent)
  lidar.rotation.x = Math.PI / 2
  lidar.position.set(0, 2.15, 1.75)
  bodyGroup.add(lidar)

  for (const side of [-1, 1]) {
    const hl = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.12, 0.06), materials.headlight)
    hl.position.set(side * 0.62, 0.85, 2.54)
    bodyGroup.add(hl)

    const tl = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.12, 0.06), materials.taillight)
    tl.position.set(side * 0.66, 0.78, -2.56)
    bodyGroup.add(tl)

    const beam = new THREE.Mesh(new THREE.PlaneGeometry(1.3, 4.0), materials.beam)
    beam.rotation.x = -Math.PI / 2
    beam.position.set(side * 0.62, 0.03, 4.55)
    group.add(beam)
  }

  group.add(bodyGroup)

  const wheelRadius = 0.4
  const tireGeo = new THREE.CylinderGeometry(wheelRadius, wheelRadius, 0.3, 18)
  const rimGeo = new THREE.CylinderGeometry(0.24, 0.24, 0.32, 12)
  for (const zPos of [1.75, -1.45]) {
    for (const side of [-1, 1]) {
      const wg = new THREE.Group()
      wg.position.set(side * 0.88, wheelRadius, zPos)
      const tire = new THREE.Mesh(tireGeo, materials.tire)
      tire.rotation.z = Math.PI / 2
      wg.add(tire)
      const rim = new THREE.Mesh(rimGeo, materials.rim)
      rim.rotation.z = Math.PI / 2
      wg.add(rim)
      group.add(wg)
      wheels.push(wg)
    }
  }

  group.scale.setScalar(scale)
  return { group, bodyGroup, wheels }
}

function addWarehouseFacility(
  parent: THREE.Group,
  mats: {
    wall: THREE.Material
    trim: THREE.Material
    roof: THREE.Material
    bayDoor: THREE.Material
    apron: THREE.Material
    lime: THREE.Material
    windowGlow: THREE.Material
  },
) {
  const facility = new THREE.Group()

  // Paved logistics service apron connecting directly to left highway shoulder (x = -7.0 to -25)
  const apron = new THREE.Mesh(new THREE.PlaneGeometry(21, 34), mats.apron)
  apron.rotation.x = -Math.PI / 2
  apron.position.set(-17.2, 0.005, -16)
  apron.receiveShadow = true
  facility.add(apron)

  // Main distribution hall
  const building = new THREE.Mesh(new THREE.BoxGeometry(10.5, 5.4, 24), mats.wall)
  building.position.set(-20.5, 2.7, -16)
  building.castShadow = true
  building.receiveShadow = true
  facility.add(building)

  // Roof fascia trim + cyber-lime smart hub perimeter line
  const roofCap = new THREE.Mesh(new THREE.BoxGeometry(10.8, 0.35, 24.3), mats.roof)
  roofCap.position.set(-20.5, 5.55, -16)
  facility.add(roofCap)

  const roofGlow = new THREE.Mesh(new THREE.BoxGeometry(10.88, 0.12, 24.38), mats.lime)
  roofGlow.position.set(-20.5, 5.25, -16)
  facility.add(roofGlow)

  // Rooftop HVAC & solar telemetry pods
  for (const zOff of [-22, -16, -10]) {
    const hvac = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.75, 2.8), mats.trim)
    hvac.position.set(-20.5, 6.08, zOff)
    hvac.castShadow = true
    facility.add(hvac)
  }

  // Architectural wall ribs & 4 illuminated loading bays facing +X (toward road apron)
  for (const zBay of [-23.5, -18.5, -13.5, -8.5]) {
    const door = new THREE.Mesh(new THREE.BoxGeometry(0.18, 3.1, 3.2), mats.bayDoor)
    door.position.set(-15.2, 1.55, zBay)
    facility.add(door)

    const dockHeader = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.14, 3.4), mats.lime)
    dockHeader.position.set(-15.18, 3.22, zBay)
    facility.add(dockHeader)

    const canopy = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.16, 3.8), mats.trim)
    canopy.position.set(-14.55, 3.45, zBay)
    canopy.castShadow = true
    facility.add(canopy)
  }

  // Office control mezzanine wing on front end of warehouse
  const officeWing = new THREE.Mesh(new THREE.BoxGeometry(5.5, 3.6, 5.5), mats.trim)
  officeWing.position.set(-18.2, 1.8, -1.6)
  officeWing.castShadow = true
  officeWing.receiveShadow = true
  facility.add(officeWing)

  const officeGlass = new THREE.Mesh(new THREE.BoxGeometry(0.12, 1.4, 4.2), mats.windowGlow)
  officeGlass.position.set(-15.42, 2.35, -1.6)
  facility.add(officeGlass)

  // Parked docked freight trailers cleanly positioned at loading bays #1 and #3 (resting on tires + landing legs)
  const dockTireGeo = new THREE.CylinderGeometry(0.42, 0.42, 0.28, 16)
  for (const zDock of [-23.5, -13.5]) {
    const dockedTrailer = new THREE.Mesh(new THREE.BoxGeometry(5.2, 2.2, 1.8), mats.bayDoor)
    dockedTrailer.position.set(-12.4, 1.55, zDock)
    dockedTrailer.castShadow = true
    dockedTrailer.receiveShadow = true
    facility.add(dockedTrailer)

    const dockStripe = new THREE.Mesh(new THREE.BoxGeometry(4.8, 0.12, 1.83), mats.lime)
    dockStripe.position.set(-12.4, 1.62, zDock)
    facility.add(dockStripe)

    // Support legs & rear wheels reaching y = 0.0 so trailer rests firmly on the apron
    const frontLeg = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.5, 1.4), mats.trim)
    frontLeg.position.set(-10.6, 0.25, zDock)
    facility.add(frontLeg)

    for (const sideZ of [-0.75, 0.75]) {
      const wheel = new THREE.Mesh(dockTireGeo, mats.roof)
      wheel.rotation.x = Math.PI / 2
      wheel.position.set(-14.0, 0.42, zDock + sideZ)
      facility.add(wheel)
    }
  }

  parent.add(facility)
}

function addRightContainerDepot(
  parent: THREE.Group,
  mats: {
    wall: THREE.Material
    trim: THREE.Material
    roof: THREE.Material
    apron: THREE.Material
    lime: THREE.Material
    containerSlate: THREE.Material
    containerTeal: THREE.Material
  },
) {
  const depot = new THREE.Group()

  // Concrete terminal pad on right side of highway (x = +7.0 to +24.5, z = -10 to +22)
  const pad = new THREE.Mesh(new THREE.PlaneGeometry(17.5, 32), mats.apron)
  pad.rotation.x = -Math.PI / 2
  pad.position.set(15.8, 0.005, 6)
  pad.receiveShadow = true
  depot.add(pad)

  // Fulfillment terminal annex
  const annex = new THREE.Mesh(new THREE.BoxGeometry(7.2, 4.1, 13), mats.wall)
  annex.position.set(19.6, 2.05, 13)
  annex.castShadow = true
  annex.receiveShadow = true
  depot.add(annex)

  const annexRoof = new THREE.Mesh(new THREE.BoxGeometry(7.5, 0.25, 13.3), mats.roof)
  annexRoof.position.set(19.6, 4.2, 13)
  depot.add(annexRoof)

  const annexStripe = new THREE.Mesh(new THREE.BoxGeometry(7.56, 0.1, 13.36), mats.lime)
  annexStripe.position.set(19.6, 3.92, 13)
  depot.add(annexStripe)

  // Organized intermodal shipping container stacks (never blocking road lanes)
  const stackSpecs: Array<{ x: number; y: number; z: number; mat: THREE.Material }> = [
    { x: 11.4, y: 0.9, z: -3.5, mat: mats.containerSlate },
    { x: 11.4, y: 2.7, z: -3.5, mat: mats.containerTeal },
    { x: 14.2, y: 0.9, z: -3.5, mat: mats.containerTeal },
    { x: 14.2, y: 0.9, z: 2.5, mat: mats.containerSlate },
    { x: 11.4, y: 0.9, z: 2.5, mat: mats.containerSlate },
    { x: 11.4, y: 0.9, z: 9.0, mat: mats.containerTeal },
    { x: 11.4, y: 2.7, z: 9.0, mat: mats.lime },
  ]

  const containerGeo = new THREE.BoxGeometry(2.1, 1.8, 5.2)
  for (const spec of stackSpecs) {
    const box = new THREE.Mesh(containerGeo, spec.mat)
    box.position.set(spec.x, spec.y, spec.z)
    box.castShadow = true
    box.receiveShadow = true
    depot.add(box)
  }

  parent.add(depot)
}

export function AutonomousWelcomeScene() {
  const mountRef = useRef<HTMLDivElement | null>(null)
  const [webglFailed, setWebglFailed] = useState(false)

  useEffect(() => {
    const container = mountRef.current
    if (!container) return

    let renderer: THREE.WebGLRenderer | null = null
    let frameId = 0
    const createdGeometries: THREE.BufferGeometry[] = []
    const createdMaterials: THREE.Material[] = []

    const prefersReducedMotion =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches

    try {
      const width = container.clientWidth || window.innerWidth
      const height = container.clientHeight || window.innerHeight
      const initialAspect = width / Math.max(1, height)

      const scene = new THREE.Scene()
      scene.fog = new THREE.FogExp2(0x0b0b0c, 0.0115)

      const camera = new THREE.PerspectiveCamera(
        initialAspect < 1 ? 50 : 39,
        initialAspect,
        0.1,
        300,
      )
      camera.position.set(20.5, 14.8, 25.5)
      camera.lookAt(0, 1.4, -2)

      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' })
      renderer.setSize(width, height)
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
      renderer.shadowMap.enabled = true
      renderer.shadowMap.type = THREE.PCFSoftShadowMap
      renderer.toneMapping = THREE.ACESFilmicToneMapping
      renderer.toneMappingExposure = 1.25
      container.innerHTML = ''
      container.appendChild(renderer.domElement)

      // Crisp 3-point + Hemisphere architectural lighting so dark logistics assets pop cleanly
      const hemiLight = new THREE.HemisphereLight(0x9fb8d6, 0x16181d, 1.05)
      scene.add(hemiLight)

      const keyLight = new THREE.DirectionalLight(0xf6faff, 2.35)
      keyLight.position.set(24, 32, 18)
      keyLight.castShadow = true
      keyLight.shadow.mapSize.set(2048, 2048)
      keyLight.shadow.camera.near = 2
      keyLight.shadow.camera.far = 120
      keyLight.shadow.camera.left = -46
      keyLight.shadow.camera.right = 46
      keyLight.shadow.camera.top = 46
      keyLight.shadow.camera.bottom = -46
      keyLight.shadow.bias = -0.0004
      scene.add(keyLight)

      const coolRimLight = new THREE.DirectionalLight(0x5d84b0, 1.05)
      coolRimLight.position.set(-26, 16, -24)
      scene.add(coolRimLight)

      const hubLimeLight = new THREE.PointLight(0xc6f432, 14, 38, 1.5)
      hubLimeLight.position.set(-12.5, 5.2, -14)

      const corridorLimeLight = new THREE.PointLight(0xc6f432, 10, 32, 1.5)
      corridorLimeLight.position.set(11.5, 5.0, 4)

      // Materials palette
      const mats = {
        ground: new THREE.MeshPhongMaterial({ color: 0x0d0e11, shininess: 12 }),
        road: new THREE.MeshPhongMaterial({ color: 0x1c1e23, specular: 0x3b404c, shininess: 32 }),
        apron: new THREE.MeshPhongMaterial({ color: 0x16181c, shininess: 18 }),
        curb: new THREE.MeshPhongMaterial({ color: 0x262930, shininess: 22 }),
        roadMark: new THREE.MeshBasicMaterial({ color: 0x5c616b }),
        limeAccent: new THREE.MeshBasicMaterial({ color: 0xc6f432 }),
        limeGlow: new THREE.MeshBasicMaterial({
          color: 0xc6f432,
          transparent: true,
          opacity: 0.85,
        }),
        cabPaint: new THREE.MeshPhongMaterial({
          color: 0x2c3038,
          specular: 0x7c8699,
          shininess: 85,
        }),
        cabTrim: new THREE.MeshPhongMaterial({ color: 0x181a1f, shininess: 40 }),
        glass: new THREE.MeshPhongMaterial({
          color: 0x111c28,
          specular: 0x99ccff,
          shininess: 120,
        }),
        trailer: new THREE.MeshPhongMaterial({
          color: 0x383c45,
          specular: 0x5a606e,
          shininess: 45,
        }),
        trailerPanel: new THREE.MeshPhongMaterial({ color: 0x464b56, shininess: 50 }),
        chassis: new THREE.MeshPhongMaterial({ color: 0x141519, shininess: 25 }),
        tire: new THREE.MeshLambertMaterial({ color: 0x16181b }),
        rim: new THREE.MeshPhongMaterial({ color: 0x9aa0aa, specular: 0xffffff, shininess: 110 }),
        headlight: new THREE.MeshBasicMaterial({ color: 0xf4ffff }),
        taillight: new THREE.MeshBasicMaterial({ color: 0xff2942 }),
        beam: new THREE.MeshBasicMaterial({
          color: 0xdffef8,
          transparent: true,
          opacity: 0.14,
          depthWrite: false,
        }),
        lampPool: new THREE.MeshBasicMaterial({
          color: 0xd8f5b8,
          transparent: true,
          opacity: 0.09,
          depthWrite: false,
        }),
        wall: new THREE.MeshPhongMaterial({ color: 0x24272d, specular: 0x454a54, shininess: 35 }),
        trim: new THREE.MeshPhongMaterial({ color: 0x30343c, shininess: 40 }),
        roof: new THREE.MeshPhongMaterial({ color: 0x191b20, shininess: 20 }),
        bayDoor: new THREE.MeshPhongMaterial({ color: 0x3f444f, shininess: 30 }),
        windowGlow: new THREE.MeshBasicMaterial({ color: 0x89c4d8 }),
        containerSlate: new THREE.MeshPhongMaterial({ color: 0x2b303a, shininess: 35 }),
        containerTeal: new THREE.MeshPhongMaterial({ color: 0x253b45, shininess: 40 }),
      }

      // Ground terrain + subtle grid lines
      const ground = new THREE.Mesh(new THREE.PlaneGeometry(240, 240), mats.ground)
      ground.rotation.x = -Math.PI / 2
      ground.position.y = -0.06
      ground.receiveShadow = true
      scene.add(ground)

      const grid = new THREE.GridHelper(180, 45, 0x2b3121, 0x181b1f)
      grid.position.y = -0.05
      scene.add(grid)

      // Master rotated logistics corridor: ALL road geometry, facilities & moving trucks live in this frame
      // so trucks strictly follow local Z lanes and can NEVER drive sideways or off-road.
      const corridorGroup = new THREE.Group()
      corridorGroup.rotation.y = CORRIDOR_ANGLE
      corridorGroup.add(hubLimeLight)
      corridorGroup.add(corridorLimeLight)
      scene.add(corridorGroup)

      const roadWidth = 13.6
      const roadLength = 152

      const road = new THREE.Mesh(new THREE.PlaneGeometry(roadWidth, roadLength), mats.road)
      road.rotation.x = -Math.PI / 2
      road.position.set(0, 0, 0)
      road.receiveShadow = true
      corridorGroup.add(road)

      // Left, Right & Center median barriers
      const outerCurbGeo = new THREE.BoxGeometry(0.45, 0.24, roadLength)
      for (const side of [-1, 1]) {
        const curb = new THREE.Mesh(outerCurbGeo, mats.curb)
        curb.position.set(side * (roadWidth / 2 + 0.15), 0.12, 0)
        curb.castShadow = true
        curb.receiveShadow = true
        corridorGroup.add(curb)

        const glowStrip = new THREE.Mesh(new THREE.PlaneGeometry(0.16, roadLength), mats.limeGlow)
        glowStrip.rotation.x = -Math.PI / 2
        glowStrip.position.set(side * (roadWidth / 2 - 0.35), 0.014, 0)
        corridorGroup.add(glowStrip)
      }

      const centerMedian = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.18, roadLength), mats.curb)
      centerMedian.position.set(0, 0.09, 0)
      centerMedian.receiveShadow = true
      corridorGroup.add(centerMedian)

      // Dashed lane dividers & median glow ticks
      const dashGeo = new THREE.PlaneGeometry(0.18, 2.6)
      const medianTickGeo = new THREE.BoxGeometry(0.12, 0.04, 1.4)
      for (let z = -70; z <= 70; z += 5.5) {
        for (const laneSplitX of [-3.4, 3.4]) {
          const dash = new THREE.Mesh(dashGeo, mats.roadMark)
          dash.rotation.x = -Math.PI / 2
          dash.position.set(laneSplitX, 0.012, z)
          corridorGroup.add(dash)
        }
        if (Math.abs(z) % 11 < 6) {
          const tick = new THREE.Mesh(medianTickGeo, mats.limeGlow)
          tick.position.set(0, 0.19, z)
          corridorGroup.add(tick)
        }
      }

      // Highway Streetlamps & Sensor Gantries
      const poleGeo = new THREE.CylinderGeometry(0.08, 0.11, 5.2, 8)
      const armGeo = new THREE.BoxGeometry(1.5, 0.1, 0.12)
      const lampHeadGeo = new THREE.BoxGeometry(0.48, 0.12, 0.24)
      const lampPoolGeo = new THREE.CircleGeometry(2.6, 20)
      for (let z = -50; z <= 50; z += 20) {
        for (const side of [-1, 1]) {
          const poleX = side * 7.45
          const pole = new THREE.Mesh(poleGeo, mats.chassis)
          pole.position.set(poleX, 2.6, z)
          corridorGroup.add(pole)

          const arm = new THREE.Mesh(armGeo, mats.chassis)
          arm.position.set(poleX - side * 0.7, 5.15, z)
          corridorGroup.add(arm)

          const head = new THREE.Mesh(lampHeadGeo, mats.headlight)
          head.position.set(poleX - side * 1.35, 5.08, z)
          corridorGroup.add(head)

          const pool = new THREE.Mesh(lampPoolGeo, mats.lampPool)
          pool.rotation.x = -Math.PI / 2
          pool.position.set(poleX - side * 1.65, 0.009, z)
          corridorGroup.add(pool)
        }
      }

      // Two Autonomous Corridor Sensor Gantries
      for (const zGantry of [-18, 12]) {
        const gantry = new THREE.Group()
        for (const side of [-1, 1]) {
          const leg = new THREE.Mesh(new THREE.BoxGeometry(0.32, 5.6, 0.32), mats.trim)
          leg.position.set(side * 7.2, 2.8, zGantry)
          leg.castShadow = true
          gantry.add(leg)
        }
        const span = new THREE.Mesh(new THREE.BoxGeometry(14.8, 0.42, 0.42), mats.trim)
        span.position.set(0, 5.45, zGantry)
        span.castShadow = true
        gantry.add(span)

        const scannerBar = new THREE.Mesh(new THREE.BoxGeometry(13.2, 0.1, 0.46), mats.limeAccent)
        scannerBar.position.set(0, 5.22, zGantry)
        gantry.add(scannerBar)

        corridorGroup.add(gantry)
      }

      // Add Smart Warehouse Hub (Left side of highway) & Container Yard Depot (Right side)
      addWarehouseFacility(corridorGroup, {
        wall: mats.wall,
        trim: mats.trim,
        roof: mats.roof,
        bayDoor: mats.bayDoor,
        apron: mats.apron,
        lime: mats.limeAccent,
        windowGlow: mats.windowGlow,
      })

      addRightContainerDepot(corridorGroup, {
        wall: mats.wall,
        trim: mats.trim,
        roof: mats.roof,
        apron: mats.apron,
        lime: mats.limeAccent,
        containerSlate: mats.containerSlate,
        containerTeal: mats.containerTeal,
      })

      // Instantiate Fleet Vehicles aligned strictly on highway lanes:
      // Right lanes (+X) move in +Z (rotation.y = 0); Left lanes (-X) move in -Z (rotation.y = Math.PI)
      const vehicles: MovingVehicle[] = []
      const vehicleSpecs: Array<{
        kind: 'semi' | 'van'
        laneX: number
        startZ: number
        speed: number
        rotY: number
        phase: number
      }> = [
          // Outbound (+Z) inner & outer lanes
          { kind: 'semi', laneX: 2.0, startZ: -38, speed: 5.4, rotY: 0, phase: 0.0 },
          { kind: 'semi', laneX: 2.0, startZ: 14, speed: 5.4, rotY: 0, phase: 1.4 },
          { kind: 'semi', laneX: 4.8, startZ: -14, speed: 4.1, rotY: 0, phase: 2.3 },
          { kind: 'van', laneX: 4.8, startZ: 38, speed: 4.1, rotY: 0, phase: 0.7 },
          // Inbound (-Z) inner & outer lanes
          { kind: 'semi', laneX: -2.0, startZ: 28, speed: -5.0, rotY: Math.PI, phase: 1.9 },
          { kind: 'semi', laneX: -2.0, startZ: -30, speed: -5.0, rotY: Math.PI, phase: 3.1 },
          { kind: 'van', laneX: -4.8, startZ: 4, speed: -6.2, rotY: Math.PI, phase: 0.4 },
        ]

      for (const spec of vehicleSpecs) {
        const built =
          spec.kind === 'semi'
            ? buildSemiTruck(mats, 0.78)
            : buildDeliveryVan(mats, 0.82)
        built.group.position.set(spec.laneX, 0, spec.startZ)
        built.group.rotation.y = spec.rotY
        corridorGroup.add(built.group)
        vehicles.push({
          group: built.group,
          bodyGroup: built.bodyGroup,
          wheels: built.wheels,
          laneZSpeed: spec.speed,
          wheelRadius: spec.kind === 'semi' ? 0.48 * 0.78 : 0.4 * 0.82,
          phaseOffset: spec.phase,
        })
      }

      // Collect geometries/materials for clean unmount disposal
      scene.traverse((obj) => {
        if (obj instanceof THREE.Mesh || obj instanceof THREE.LineSegments) {
          createdGeometries.push(obj.geometry)
          if (Array.isArray(obj.material)) {
            createdMaterials.push(...obj.material)
          } else {
            createdMaterials.push(obj.material)
          }
        }
      })

      // Subtle camera parallax based on cursor position
      let targetCamX = 20.5
      let targetCamY = 14.8
      const baseCamZ = 25.5

      const onMouseMove = (e: MouseEvent) => {
        if (prefersReducedMotion) return
        const mx = (e.clientX / window.innerWidth) * 2 - 1
        const my = -(e.clientY / window.innerHeight) * 2 + 1
        targetCamX = 20.5 + mx * 2.2
        targetCamY = 14.8 - my * 1.4
      }
      window.addEventListener('mousemove', onMouseMove, { passive: true })

      const onResize = () => {
        if (!renderer || !container) return
        const w = container.clientWidth || window.innerWidth
        const h = container.clientHeight || window.innerHeight
        const aspect = w / Math.max(1, h)
        camera.fov = aspect < 1 ? 50 : 39
        camera.aspect = aspect
        camera.updateProjectionMatrix()
        renderer.setSize(w, h)
      }
      window.addEventListener('resize', onResize)

      const clock = new THREE.Clock()

      const animate = () => {
        frameId = window.requestAnimationFrame(animate)
        const delta = Math.min(clock.getDelta(), 0.05)
        const elapsed = clock.getElapsedTime()

        camera.position.x += (targetCamX - camera.position.x) * 0.05
        camera.position.y += (targetCamY - camera.position.y) * 0.05
        camera.position.z = baseCamZ
        camera.lookAt(0, 1.4, -2)

        if (!prefersReducedMotion) {
          for (const v of vehicles) {
            v.group.position.z += v.laneZSpeed * delta

            // Wrap seamlessly outside visible fog range
            if (v.laneZSpeed > 0 && v.group.position.z > TRACK_MAX_Z) {
              v.group.position.z -= TRACK_SPAN
            } else if (v.laneZSpeed < 0 && v.group.position.z < TRACK_MIN_Z) {
              v.group.position.z += TRACK_SPAN
            }

            // Wheel rotation matches forward speed on the truck's local +Z axis
            const angularStep = (Math.abs(v.laneZSpeed) / v.wheelRadius) * delta
            for (const w of v.wheels) {
              w.rotation.x += angularStep
            }

            // Subtle body-only suspension micro-motion (wheels remain locked flush on asphalt y = 0)
            v.bodyGroup.position.y = Math.sin(elapsed * 4.2 + v.phaseOffset) * 0.015
          }

          hubLimeLight.intensity = 13 + Math.sin(elapsed * 1.6) * 2
        }

        renderer?.render(scene, camera)
      }

      animate()

      return () => {
        window.cancelAnimationFrame(frameId)
        window.removeEventListener('mousemove', onMouseMove)
        window.removeEventListener('resize', onResize)

        const uniqueGeos = new Set(createdGeometries)
        uniqueGeos.forEach((g) => g.dispose())
        const uniqueMats = new Set(createdMaterials)
        uniqueMats.forEach((m) => m.dispose())

        if (renderer) {
          renderer.dispose()
          renderer.domElement.remove()
        }
      }
    } catch {
      setWebglFailed(true)
      return undefined
    }
  }, [])

  if (webglFailed) {
    return (
      <div
        aria-label="WebGL fallback grid"
        className="absolute inset-0 opacity-25"
        style={{
          backgroundImage:
            'linear-gradient(to right, #c6f432 1px, transparent 1px), linear-gradient(to bottom, #c6f432 1px, transparent 1px)',
          backgroundSize: '48px 48px',
        }}
      />
    )
  }

  return <div ref={mountRef} className="absolute inset-0 h-full w-full overflow-hidden" />
}
