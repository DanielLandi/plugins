// 3D model files are bundled as URLs (webpack-override.ts).
declare module '*.glb' {
  const url: string;
  export default url;
}

// VRM characters (glTF with the VRM extension) are bundled as URLs too: '@mv/avatars/<file>.vrm' or './<file>.vrm'.
declare module '*.vrm' {
  const url: string;
  export default url;
}
