#version 400
//#ifdef GL_ES
//precision mediump float;
//#endif

in vec2 texCoord;  // always [0, 1] takes into account screen resolution
out vec4 fragColor;

uniform float Red = 0.0;
uniform float Green = 0.0;
uniform float Blue = 0.0;

void main(){
  fragColor = vec4(vec3(Red, Green, Blue), 1.);
}
