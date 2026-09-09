// Display-only playback. Clip indices (not names) distinguish duplicate names.
export function createAnimationPlayback(mixer, clips) {
  let index = clips.length ? 0 : -1;
  let playing = false;
  let speed = 1;
  let disposed = false;
  let action = null;

  function activate() {
    mixer.stopAllAction();
    action = mixer.clipAction(clips[index]);
    action.reset().play();
    action.paused = !playing;
    mixer.update(0);
  }

  function state() {
    return {index, playing, speed, time: action?.time || 0,
      duration: index < 0 ? 0 : clips[index].duration};
  }

  return {
    state,
    select(next) {
      if (disposed || !Number.isInteger(next) || next < 0 || next >= clips.length) return false;
      index = next;
      activate();
      return true;
    },
    toggle() {
      if (disposed || index < 0) return false;
      playing = !playing;
      if (!action) activate();
      action.paused = !playing;
      return playing;
    },
    restart() {
      if (!disposed && index >= 0) activate();
    },
    setSpeed(next) {
      if (disposed || ![0.25, 0.5, 1, 2].includes(next)) return false;
      speed = next;
      return true;
    },
    update(delta) {
      if (!disposed && playing && Number.isFinite(delta) && delta >= 0) mixer.update(delta * speed);
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      playing = false;
      mixer.stopAllAction();
      for (const clip of clips) mixer.uncacheAction(clip);
      action = null;
    },
  };
}
