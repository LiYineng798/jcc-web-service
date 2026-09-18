importScripts(new URLSearchParams(self.location.search).get('engine'));
self.onmessage = ({ data }) => {
  try {
    const result = TraitLadder.solve(data.data, data.options, progress => self.postMessage({ progress }));
    self.postMessage({ result });
  } catch (error) { self.postMessage({ error: error.message }); }
};
