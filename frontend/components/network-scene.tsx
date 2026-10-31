'use client';
import { Component, useMemo, useRef, useState, type ReactNode } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Float, Line, RoundedBox } from '@react-three/drei';
import * as THREE from 'three';
import { usePreferences } from './providers';

const NODES: [number, number, number][] = [[1.9,0.65,0.4],[-1.6,1.15,0.1],[0.25,1.9,-0.4],[0.5,-1.8,0.8],[-1.35,-1.1,-0.8],[1.2,0.1,-1.65]];
function Connections({ energized }: { energized: boolean }) {
  const particles = useMemo(() => {
    const values = new Float32Array(180);
    for (let i=0; i<60; i++) { const t = i*2.39996; const r = 2.35 + Math.sin(i*7.31)*0.8; values[i*3] = Math.cos(t)*r; values[i*3+1] = Math.sin(t)*r*0.85; values[i*3+2] = Math.sin(i*3.71)*1.7; }
    return values;
  }, []);
  return <group>{NODES.map((node, i) => <group key={i}><Line points={[[0,0,0], node]} color={i%2 ? '#63D9E8' : '#7892FF'} transparent opacity={energized ? 0.65 : 0.24} lineWidth={0.7}/><Line points={[node, NODES[(i+1)%NODES.length]]} color="#6681C7" transparent opacity={0.2} lineWidth={0.6}/><mesh position={node}><sphereGeometry args={[i===0 ? 0.14 : 0.09, 20, 20]}/><meshStandardMaterial color={i%2 ? '#9DE8ED' : '#A9BAFF'} emissive={i%2 ? '#63D9E8' : '#5B7CFF'} emissiveIntensity={energized ? 1.5 : 0.45} metalness={0.4} roughness={0.2}/></mesh><mesh position={node}><sphereGeometry args={[0.19,16,16]}/><meshBasicMaterial color="#5B7CFF" transparent opacity={0.07}/></mesh></group>)}<points><bufferGeometry><bufferAttribute attach="attributes-position" args={[particles,3]}/></bufferGeometry><pointsMaterial size={0.019} color="#8EABC9" transparent opacity={0.65} sizeAttenuation/></points></group>;
}
function Structure({ scroll, energized }: { scroll: number; energized: boolean }) {
  const group = useRef<THREE.Group>(null); const inner = useRef<THREE.Group>(null); const { reduced } = usePreferences();
  useFrame((state, delta) => {
    if (!group.current) return;
    const targetY = state.pointer.x*0.2 + scroll*0.5 + (reduced ? 0.3 : state.clock.elapsedTime*0.035);
    const targetX = -state.pointer.y*0.12 + scroll*0.15;
    group.current.rotation.y = THREE.MathUtils.damp(group.current.rotation.y, targetY, 3, delta);
    group.current.rotation.x = THREE.MathUtils.damp(group.current.rotation.x, targetX, 3, delta);
    if (inner.current && !reduced) inner.current.rotation.z += delta*(energized ? 0.2 : 0.035);
    state.camera.position.z = THREE.MathUtils.damp(state.camera.position.z, 7.5+scroll*0.8, 3, delta);
  });
  return <group ref={group} rotation={[0.1,0.3,-0.14]}><group ref={inner}><mesh rotation={[1.05,0.3,0.25]}><torusGeometry args={[2.05,0.066,16,120]}/><meshPhysicalMaterial color="#5275EB" metalness={0.72} roughness={0.25} clearcoat={1}/></mesh><mesh rotation={[0.35,0.9,-0.55]}><torusGeometry args={[2.12,0.047,16,120]}/><meshPhysicalMaterial color="#8495BC" metalness={0.85} roughness={0.2} clearcoat={1}/></mesh><mesh rotation={[0.55,-0.65,0.8]}><torusGeometry args={[1.96,0.025,12,120]}/><meshStandardMaterial color="#63D9E8" emissive="#256D83" emissiveIntensity={0.4} metalness={0.6} roughness={0.25}/></mesh></group><Float speed={reduced ? 0 : 1.2} rotationIntensity={reduced ? 0 : 0.12} floatIntensity={reduced ? 0 : 0.25}><RoundedBox args={[1.05,1.05,1.05]} radius={0.15} smoothness={4} rotation={[0.5,0.6,0.15]}><meshPhysicalMaterial color="#8099F6" metalness={0.62} roughness={0.2} clearcoat={1}/></RoundedBox><RoundedBox args={[0.64,0.64,0.64]} radius={0.07} smoothness={3} rotation={[0.5,0.6,0.15]} position={[0.6,0.48,-0.25]}><meshPhysicalMaterial color="#B1E7ED" metalness={0.55} roughness={0.22} clearcoat={1}/></RoundedBox></Float><Connections energized={energized}/></group>;
}
export function NetworkFallback() { return <div className="network-fallback" aria-hidden="true"><svg viewBox="0 0 500 500"><defs><linearGradient id="orbit-gradient"><stop stopColor="#5B7CFF"/><stop offset="1" stopColor="#63D9E8"/></linearGradient></defs><g fill="none" stroke="url(#orbit-gradient)" strokeWidth="2"><ellipse cx="250" cy="250" rx="185" ry="85" transform="rotate(-30 250 250)"/><ellipse cx="250" cy="250" rx="180" ry="90" transform="rotate(65 250 250)"/><ellipse cx="250" cy="250" rx="170" ry="110" transform="rotate(150 250 250)"/><path d="m100 170 150 80 150-110M250 250l-70 150m70-150 155 90" opacity=".4"/></g><rect x="211" y="211" width="78" height="78" rx="15" fill="#7895F5" transform="rotate(25 250 250)"/>{[[100,170],[400,140],[180,400],[405,340]].map(([x,y]) => <circle key={x} cx={x} cy={y} r="7" fill="#9BDDE8"/>)}</svg></div>; }
class SceneBoundary extends Component<{ children: ReactNode }, { failed: boolean }> { state = { failed: false }; static getDerivedStateFromError() { return { failed: true }; } render() { return this.state.failed ? <NetworkFallback/> : this.props.children; } }
export default function NetworkScene({ scroll = 0, energized = false }: { scroll?: number; energized?: boolean }) {
  const { reduced } = usePreferences(); const [ready, setReady] = useState(false);
  return <SceneBoundary>{!ready && <NetworkFallback/>}<Canvas camera={{ position: [0,0,7.5], fov: 43 }} dpr={[1,1.5]} frameloop={reduced ? 'demand' : 'always'} gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }} fallback={<NetworkFallback/>} onCreated={() => setReady(true)} style={{ opacity: ready ? 1 : 0, transition: 'opacity 0.7s' }} aria-label="Interactive sculpture of connected conversations and commitments"><ambientLight intensity={1.1}/><directionalLight position={[4,6,5]} intensity={3.5} color="#DCE5FF"/><directionalLight position={[-4,-2,3]} intensity={2} color="#63D9E8"/><pointLight position={[0,2,-3]} intensity={16} color="#5B7CFF"/><Structure scroll={scroll} energized={energized}/></Canvas></SceneBoundary>;
}
