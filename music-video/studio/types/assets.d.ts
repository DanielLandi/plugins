// 3D model files are bundled as URLs (webpack-override.ts).
declare module '*.glb' {
  const url: string;
  export default url;
}
