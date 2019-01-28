#version 400
#ifdef GL_ES
precision mediump float;
#endif

in vec2 texCoord;  // always [0, 1] takes into account screen resolution
out vec4 fragColor;

//#extension GL_OES_standard_derivatives : enable
#define M_PI 3.14159265358979
//uniform vec2 xc = vec2(0.5, 1.);
//uniform vec2 texCoord = gl_FragCoord.xy;
uniform float patch_size = 30.; // in degrees
uniform float gabor_angle = 0.; // in degrees
uniform float gabor_freq = 0.19; // cycle per deg
uniform float gabor_contrast = 1.0; // [0, 1]
uniform float gabor_phase = 0. * M_PI; //in radian
uniform float locationX = 0.5;  // E[0,1] from rotary encoder [-1,1]
uniform float locationY = 0.5;  // E[0,1]
//uniform int frame_count = 0;
uniform int color = 0;
uniform float R = 0.5;
uniform float G = 0.5;
uniform float B = 0.5;
uniform float brightness = 0.5;
uniform float sync_square_x = 0.95;
uniform float sync_square_y = 0.17;

float gauss(float val, float sigma) {
    return exp(-(val * val) / (2. * sigma * sigma));
}

void main(){
//    float locationX = xc[0];
//    float gabor_contrast = xc[1];
    float positionX = ((locationX + 1.) / 2.); // transforms [-1, 1] -> [0, 1]
    // TODO: ticks/normalized ticks to deg/tick using gain
    float patch_size_rad = patch_size / 180.* M_PI; //in radian view angle
    float gabor_angle_rad = gabor_angle / 180. * M_PI; //in radian view angle
    float gabor_freq_ncycles = gabor_freq * 360.; // cycle per entire view rotation (360 deg)
    float locationRX = (positionX * 270. - 135.) / 180. * M_PI; //[0, 1] -> [-3/4pi, 3/4pi]
    float screenDist = 1. / 2.; // assumes equidistand mouse
    float rect = 0.;

    if (texCoord.x > sync_square_x && texCoord.y < sync_square_y ) {
        fragColor = vec4(vec3(color), 1.0);
    } else {

    float X = texCoord.x-(1./2.);
    float Y = texCoord.y-(1./2.);
    float RX = atan(X / screenDist);
    float RY = atan(Y / sqrt(screenDist * screenDist + X * X));
    float RXrot = cos(gabor_angle_rad) * (RX - locationRX) + sin(gabor_angle_rad) * RY;
    float grating = gabor_contrast * sin((gabor_freq_ncycles * RXrot) + gabor_phase);

    float RDist = acos((X * sin(locationRX) + Y * 0. + screenDist * cos(locationRX)) / sqrt(X * X + Y * Y + screenDist * screenDist) * 1.);
    float gaussian = gauss(RDist, patch_size_rad);

    float value = gaussian * grating;
    fragColor = vec4(brightness + vec3(R * value, G * value, B * value), 1.0);
  }
}
