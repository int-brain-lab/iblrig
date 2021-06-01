#version 400
uniform float aspectRatio = 1;
uniform vec2 scale = vec2(1, 1);
uniform vec2 shift;
layout(location = 0) in vec2 vp;
layout(location = 1) in vec2 vt;
out vec2 texCoord;

void main()
{
  vec2 pos = vec2(vp.x, vp.y * aspectRatio);
  gl_Position = vec4(pos * scale + shift, 0.0, 1.0);
  texCoord = vt;
}
