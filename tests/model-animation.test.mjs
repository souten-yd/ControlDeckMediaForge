import assert from "node:assert/strict";
import {test} from "node:test";
import * as THREE from "three";
import {createAnimationPlayback} from "../frontend/model-animation.mjs";

function fixture() {
  const root = new THREE.Object3D();
  const clips = [1, 10].map((end) => new THREE.AnimationClip("duplicate name", 2,
    [new THREE.NumberKeyframeTrack(".position[x]", [0, 2], [0, end])]));
  const mixer = new THREE.AnimationMixer(root);
  return {root, clips, mixer, player: createAnimationPlayback(mixer, clips)};
}

test("only the selected clip affects the real Three mixer", () => {
  const {root, player} = fixture();
  assert.equal(player.toggle(), true);
  player.update(1);
  assert.equal(root.position.x, 0.5);
  assert.equal(player.select(1), true);
  assert.equal(root.position.x, 0);
  player.update(1);
  assert.equal(root.position.x, 5); // Not blended with the first action.
  assert.equal(player.state().index, 1);
});

test("pause, selection, restart, resume and speed preserve explicit state", () => {
  const {root, player} = fixture();
  player.toggle(); player.update(1); player.toggle();
  player.update(1); assert.equal(root.position.x, 0.5);
  player.select(1); assert.equal(player.state().playing, false);
  player.update(1); assert.equal(root.position.x, 0);
  player.setSpeed(0.5); player.toggle(); player.update(1);
  assert.equal(root.position.x, 2.5);
  player.restart(); assert.equal(root.position.x, 0);
  assert.equal(player.state().playing, true);
  player.update(1); assert.equal(root.position.x, 2.5);
  player.toggle(); player.restart(); assert.equal(root.position.x, 0);
  assert.equal(player.state().playing, false);
});

test("invalid selections/speeds do not change the running action", () => {
  const {player} = fixture();
  player.toggle(); player.update(1);
  const before = player.state();
  for (const value of [-1, 2, 0.5, NaN, '1', null]) assert.equal(player.select(value), false);
  for (const value of [0, -1, 100, Infinity, '2', null]) assert.equal(player.setSpeed(value), false);
  player.update(NaN); player.update(-1);
  assert.deepEqual(player.state(), before);
});

test("empty and disposed players cannot activate actions", () => {
  const empty = createAnimationPlayback(new THREE.AnimationMixer(new THREE.Object3D()), []);
  assert.equal(empty.toggle(), false); assert.equal(empty.select(0), false);
  empty.restart(); empty.dispose(); empty.dispose();
  const {root, mixer, player} = fixture();
  player.toggle(); player.update(1); player.dispose(); player.dispose();
  assert.equal(root.position.x, 0);
  assert.equal(mixer.stats.actions.inUse, 0);
  assert.equal(mixer.stats.actions.total, 0);
  assert.equal(player.toggle(), false); assert.equal(player.select(0), false);
  assert.equal(player.setSpeed(2), false);
  player.restart(); player.update(1); assert.equal(root.position.x, 0);
});

test("switching disjoint tracks restores old properties without changing clip data", () => {
  const root = new THREE.Object3D();
  const clips = ["x", "y"].map((axis) => new THREE.AnimationClip(axis, 2,
    [new THREE.NumberKeyframeTrack(`.position[${axis}]`, [0, 2], [0, 10])]));
  const original = clips.map((clip) => JSON.stringify(THREE.AnimationClip.toJSON(clip)));
  const player = createAnimationPlayback(new THREE.AnimationMixer(root), clips);
  player.toggle(); player.update(1); assert.equal(root.position.x, 5);
  player.select(1); player.update(1);
  assert.equal(root.position.x, 0); assert.equal(root.position.y, 5);
  assert.deepEqual(clips.map((clip) => JSON.stringify(THREE.AnimationClip.toJSON(clip))), original);
});
