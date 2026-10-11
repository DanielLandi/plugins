import { Config } from '@remotion/cli/config';
import { webpackOverride } from './webpack-override';

Config.setVideoImageFormat('jpeg');
Config.setCodec('h264');
Config.setOverwriteOutput(true);
// tools/remotion.mjs passes each video's --gl mode from its video.yaml; this is the default.
Config.setChromiumOpenGlRenderer('angle');
// 3D models (.glb) are imported as files; the same override is passed to bundle() in tools/*.ts.
Config.overrideWebpackConfig(webpackOverride);
