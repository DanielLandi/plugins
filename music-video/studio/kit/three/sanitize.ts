/**
 * A post-processing pass for right after the scene render: NaN and infinite pixels become black and very bright ones
 * are capped, so bloom cannot spread them. One bad HDR pixel (a highlight overflowing half float, a 0/0 in a shader)
 * blurred into a third of the frame, which then showed as blank (single "flash" frames in a draft).
 * Use: `composer.addPass(new ShaderPass(SanitizeShader))` after the RenderPass.
 */
export const SanitizeShader = {
  uniforms: { tDiffuse: { value: null }, maxValue: { value: 64 } },
  vertexShader: `varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: `uniform sampler2D tDiffuse; uniform float maxValue; varying vec2 vUv;
    void main() {
      vec4 c = texture2D(tDiffuse, vUv);
      bool bad = any(isnan(c)) || any(isinf(c));
      gl_FragColor = bad ? vec4(0.0, 0.0, 0.0, 1.0) : vec4(clamp(c.rgb, 0.0, maxValue), clamp(c.a, 0.0, 1.0));
    }`,
};
