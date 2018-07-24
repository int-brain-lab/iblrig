#version 400
in vec2 texCoord;
out vec4 fragColor;

uniform float patch_size = 40.; //transform this in degrees of visual field
uniform float gabor_angle = 45.;
uniform float gabor_freq = 10.;
uniform float gabor_contrast = 0.5;
uniform float locationX = .5;
uniform float locationY = .5;

#define M_PI 3.14159265358979
float gauss(float val, float size)
{
  return exp(-(val * val) * size); 
}

void main()
{
  float rad = gabor_angle * M_PI / 180.;
  vec2 uv = texCoord;
  float g = gauss(uv.x - locationX, patch_size)* 
            gauss(uv.y - locationY, patch_size);

  float s = gabor_contrast * sin((cos(rad) * uv.x + sin(rad) * uv.y) * gabor_freq * M_PI);
  fragColor = vec4(.5 + vec3(g * s), 1.0);
}