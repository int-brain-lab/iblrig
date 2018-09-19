#version 400
#ifdef GL_ES
precision mediump float;
#endif

in vec2 texCoord;  // always [0, 1] takes into account screen resolution
out vec4 fragColor;

//#extension GL_OES_standard_derivatives : enable
#define M_PI 3.14159265358979

//uniform vec2 texCoord = gl_FragCoord.xy;
uniform float patch_size = 30.; // in degrees
uniform float gabor_angle = 0.; // in degrees
uniform float gabor_freq = 0.19; // cycle per deg
uniform float gabor_contrast = 1.0; // [0, 1]
uniform float gabor_phase = 0. * M_PI; //in radian
uniform float locationX = 0.5;  // E[0,1] from rotary encoder [-1,1]
uniform float locationY = 0.5;  // E[0,1]
uniform int frame_count = 0;
uniform float color = 1.;

float gauss(float val, float sigma) {
    return exp(-(val * val) / (2. * sigma * sigma));
}

void main(){
    float positionX = ((locationX + 1.) / 2.); // transforms [-1, 1] -> [0, 1]
    // TODO: ticks/normalized ticks to deg/tick using gain
    float patch_size_rad = patch_size / 180.* M_PI; //in radian view angle
    float gabor_angle_rad = gabor_angle / 180. * M_PI; //in radian view angle
    float gabor_freq_ncycles = gabor_freq * 360.; // cycle per entire view rotation (360 deg)
    float locationRX = (positionX*270. - 135.) / 180. * M_PI; //[0, 1] -> [-3/4pi, 3/4pi]
    float screenDist = 1./6.; // assumes equidistand mouse
    float rect = 0.;
    float square_color = color;

    if (texCoord.x > 0.95 && texCoord.y < 0.275 ) {
        if(frame_count % 2 == 0){
            //square_color = 1. - square_color;
            fragColor = vec4(vec3(square_color), 1.0);
        } //else if (frame_count % 2 != 0){}
    } else if (texCoord.x < 1./3.) { //here assume left 1/3 is left screen
    float X = texCoord.x-(1./6.); //relative to left screen center
    float Y = texCoord.y-(1./2.); //relative to screen center
    float RX = atan(X/screenDist) - M_PI/2.; //azimuth
    float RY = atan(Y/sqrt(screenDist*screenDist + X*X)); //elevation
    float RXrot = cos(gabor_angle_rad)*(RX-locationRX) + sin(gabor_angle_rad)*RY; //x coordinate after rotating -gabor_angle_rad
    float grating = gabor_contrast * sin((gabor_freq_ncycles * RXrot) + gabor_phase); //grating value (-1 - 1) at RXrot
    //float grating = 1.;

    float RDist = acos(((-screenDist)*sin(locationRX) + Y*0. + X*cos(locationRX)) / sqrt(screenDist*screenDist + Y*Y + X*X)*1. ); //ab = |a||b|cos(theta)
    float gaussian = gauss(RDist, patch_size_rad);
    //float gaussian = 1.;

    fragColor = vec4(0.5 + 0.5 * vec3(gaussian * grating), 1.0);

    } else if (texCoord.x < 1.*2./3.) { //here assume 1/3-2/3 is front screen

    float X = texCoord.x-(1./2.);
    float Y = texCoord.y-(1./2.);
    float RX = atan(X/screenDist);
    float RY = atan(Y/sqrt(screenDist*screenDist + X*X));
    float RXrot = cos(gabor_angle_rad)*(RX-locationRX) + sin(gabor_angle_rad)*RY;
    float grating = gabor_contrast * sin((gabor_freq_ncycles * RXrot) + gabor_phase);
    //float grating = 1.;

    float RDist = acos((X*sin(locationRX) + Y*0. + screenDist*cos(locationRX)) / sqrt(X*X + Y*Y + screenDist*screenDist)*1.);
    float gaussian = gauss(RDist, patch_size_rad);
    //float gaussian = 1.;

    fragColor = vec4(0.5 + 0.5 * vec3(gaussian * grating), 1.0);

    } else { // the rest is right screen

    float X = texCoord.x-(1.*5./6.); //relative to right screen center
    float Y = texCoord.y-(1./2.);
    float RX = atan(X/screenDist) + M_PI/2.;
    float RY = atan(Y/sqrt(screenDist*screenDist + X*X));
    float RXrot = cos(gabor_angle_rad)*(RX-locationRX) + sin(gabor_angle_rad)*RY;
    float grating = gabor_contrast * sin((gabor_freq_ncycles * RXrot) + gabor_phase);
    //float grating = 1.;

    float RDist = acos((screenDist*sin(locationRX) + Y*0. + (-X)*cos(locationRX)) / sqrt(screenDist*screenDist + Y*Y + X*X)*1.);
    float gaussian = gauss(RDist, patch_size_rad);
    //float gaussian = 1.;

    fragColor = vec4(0.5 + 0.5 * vec3(gaussian * grating), 1.0);
  }
}
