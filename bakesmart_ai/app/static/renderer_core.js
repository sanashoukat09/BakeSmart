(() => {
  "use strict";

  const VS = `
    precision highp float;
    attribute vec3 aPosition;
    attribute vec3 aNormal;
    attribute vec3 aColor;
    attribute vec3 aVertexMaterial;
    attribute vec2 aUv;
    uniform mat4 uModel;
    uniform mat4 uViewProj;
    uniform float uShadowPass;
    varying vec3 vNormal;
    varying vec3 vColor;
    varying vec3 vVertexMaterial;
    varying vec2 vUv;
    varying vec3 vWorldPosition;
    void main() {
      vec4 world = uModel * vec4(aPosition, 1.0);
      vWorldPosition = world.xyz;
      vNormal = normalize(mat3(uModel) * aNormal);
      vColor = aColor;
      vVertexMaterial = aVertexMaterial;
      vUv = aUv;
      if (uShadowPass > 0.5) {
        float height = max(world.y, 0.0);
        world.x += height * 0.14;
        world.z += height * 0.10;
        world.y = 0.006;
      }
      gl_Position = uViewProj * world;
    }
  `;

  const FS = `
    precision highp float;
    varying vec3 vNormal;
    varying vec3 vColor;
    varying vec3 vVertexMaterial;
    varying vec2 vUv;
    varying vec3 vWorldPosition;
    uniform float uShadowPass;
    uniform float uPickPass;
    uniform vec3 uPickColor;
    uniform float uSelected;
    uniform vec4 uBaseColorFactor;
    uniform float uMetallicFactor;
    uniform float uRoughnessFactor;
    uniform vec3 uEmissiveFactor;
    uniform float uHasVertexMaterial;
    uniform float uHasBaseColorTexture;
    uniform float uHasMetalRoughTexture;
    uniform float uHasEmissiveTexture;
    uniform sampler2D uBaseColorTexture;
    uniform sampler2D uMetalRoughTexture;
    uniform sampler2D uEmissiveTexture;

    void main() {
      if (uPickPass > 0.5) {
        gl_FragColor = vec4(uPickColor, 1.0);
        return;
      }
      if (uShadowPass > 0.5) {
        float fade = clamp(0.28 - max(vWorldPosition.y, 0.0) * 0.025, 0.12, 0.28);
        gl_FragColor = vec4(0.14, 0.10, 0.12, fade);
        return;
      }

      vec3 normal = normalize(vNormal);
      vec3 keyLight = normalize(vec3(0.48, 0.82, 0.30));
      vec3 fillLight = normalize(vec3(-0.54, 0.36, 0.76));
      vec3 viewDirection = normalize(vec3(0.0, 0.25, 1.0));
      vec4 sampledBase = texture2D(uBaseColorTexture, vUv);
      vec3 albedo = clamp(
        uBaseColorFactor.rgb * vColor * mix(vec3(1.0), sampledBase.rgb, uHasBaseColorTexture),
        0.0, 1.0
      );
      float alpha = uBaseColorFactor.a * mix(1.0, sampledBase.a, uHasBaseColorTexture);
      float metallic = uMetallicFactor;
      float roughness = uRoughnessFactor;
      float localEmissive = 0.0;
      if (uHasVertexMaterial > 0.5) {
        metallic = vVertexMaterial.x;
        roughness = vVertexMaterial.y;
        localEmissive = vVertexMaterial.z;
      }
      vec4 mr = texture2D(uMetalRoughTexture, vUv);
      metallic *= mix(1.0, mr.b, uHasMetalRoughTexture);
      roughness *= mix(1.0, mr.g, uHasMetalRoughTexture);
      metallic = clamp(metallic, 0.0, 1.0);
      roughness = clamp(roughness, 0.06, 1.0);

      float keyDiffuse = max(dot(normal, keyLight), 0.0);
      float fillDiffuse = max(dot(normal, fillLight), 0.0);
      float hemisphere = normal.y * 0.5 + 0.5;
      vec3 halfVector = normalize(keyLight + viewDirection);
      float specularPower = mix(108.0, 6.0, roughness);
      float specularTerm = pow(max(dot(normal, halfVector), 0.0), specularPower);
      vec3 fresnel0 = mix(vec3(0.04), albedo, metallic);
      vec3 diffuseColor = albedo * (1.0 - metallic);
      vec3 ambient = mix(vec3(0.22, 0.23, 0.26), vec3(0.52, 0.49, 0.46), hemisphere);
      vec3 lit = diffuseColor * (
        ambient + vec3(1.08, 0.98, 0.90) * keyDiffuse * 0.86 +
        vec3(0.82, 0.90, 1.0) * fillDiffuse * 0.24
      );
      lit += fresnel0 * specularTerm * mix(0.82, 0.12, roughness);
      float rim = pow(1.0 - max(dot(normal, viewDirection), 0.0), 3.0);
      lit += albedo * rim * 0.045;
      vec3 sampledEmissive = texture2D(uEmissiveTexture, vUv).rgb;
      vec3 emissive = uEmissiveFactor * mix(vec3(1.0), sampledEmissive, uHasEmissiveTexture);
      lit += emissive + albedo * localEmissive * 0.75;
      if (uSelected > 0.5) {
        lit = mix(lit, vec3(1.0, 0.58, 0.72), 0.17 + rim * 0.16);
      }
      lit = pow(clamp(lit, 0.0, 1.0), vec3(0.90));
      gl_FragColor = vec4(lit, alpha);
    }
  `;

  const COMPONENT_BYTES = { 5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4 };
  const COMPONENTS = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT4: 16 };
  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

  function identity() {
    return new Float32Array([1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]);
  }

  function multiply(left, right) {
    const out = new Float32Array(16);
    for (let c = 0; c < 4; c += 1) {
      for (let r = 0; r < 4; r += 1) {
        out[c * 4 + r] =
          left[r] * right[c * 4] + left[4 + r] * right[c * 4 + 1] +
          left[8 + r] * right[c * 4 + 2] + left[12 + r] * right[c * 4 + 3];
      }
    }
    return out;
  }

  function translation(x, y, z) {
    const out = identity(); out[12] = x; out[13] = y; out[14] = z; return out;
  }

  function scaling(x, y, z) {
    const out = identity(); out[0] = x; out[5] = y; out[10] = z; return out;
  }

  function quaternionMatrix(q) {
    const [x,y,z,w] = q, x2=x+x, y2=y+y, z2=z+z;
    const xx=x*x2, xy=x*y2, xz=x*z2, yy=y*y2, yz=y*z2, zz=z*z2, wx=w*x2, wy=w*y2, wz=w*z2;
    return new Float32Array([
      1-(yy+zz), xy+wz, xz-wy, 0,
      xy-wz, 1-(xx+zz), yz+wx, 0,
      xz+wy, yz-wx, 1-(xx+yy), 0,
      0,0,0,1,
    ]);
  }

  function nodeMatrix(node) {
    if (Array.isArray(node.matrix) && node.matrix.length === 16) return new Float32Array(node.matrix);
    const t=node.translation||[0,0,0], r=node.rotation||[0,0,0,1], s=node.scale||[1,1,1];
    return multiply(translation(...t), multiply(quaternionMatrix(r), scaling(...s)));
  }

  function perspective(fovy, aspect, near, far) {
    const f=1/Math.tan(fovy/2), range=1/(near-far);
    return new Float32Array([f/aspect,0,0,0, 0,f,0,0, 0,0,(far+near)*range,-1, 0,0,2*far*near*range,0]);
  }

  function normalize(v) { const l=Math.hypot(...v)||1; return [v[0]/l,v[1]/l,v[2]/l]; }
  function cross(a,b) { return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]; }
  function lookAt(eye,target,up) {
    const z=normalize([eye[0]-target[0],eye[1]-target[1],eye[2]-target[2]]), x=normalize(cross(up,z)), y=cross(z,x);
    return new Float32Array([
      x[0],y[0],z[0],0, x[1],y[1],z[1],0, x[2],y[2],z[2],0,
      -(x[0]*eye[0]+x[1]*eye[1]+x[2]*eye[2]),
      -(y[0]*eye[0]+y[1]*eye[1]+y[2]*eye[2]),
      -(z[0]*eye[0]+z[1]*eye[1]+z[2]*eye[2]),1,
    ]);
  }

  function transformPoint(m,p) {
    const [x,y,z]=p, w=m[3]*x+m[7]*y+m[11]*z+m[15]||1;
    return [(m[0]*x+m[4]*y+m[8]*z+m[12])/w,(m[1]*x+m[5]*y+m[9]*z+m[13])/w,(m[2]*x+m[6]*y+m[10]*z+m[14])/w];
  }

  function parseGlb(buffer, sourceUrl) {
    const view=new DataView(buffer);
    if (view.byteLength<20 || view.getUint32(0,true)!==0x46546c67) throw new Error("invalid GLB header");
    if (view.getUint32(4,true)!==2 || view.getUint32(8,true)!==view.byteLength) throw new Error("unsupported GLB version or declared length");
    let offset=12, document=null, binaryStart=-1;
    while (offset+8<=view.byteLength) {
      const length=view.getUint32(offset,true), type=view.getUint32(offset+4,true), start=offset+8;
      if (start+length>view.byteLength) throw new Error("GLB chunk exceeds file length");
      if (type===0x4e4f534a) document=JSON.parse(new TextDecoder().decode(new Uint8Array(buffer,start,length)).trim());
      else if (type===0x004e4942) binaryStart=start;
      offset=start+length;
    }
    if (!document || binaryStart<0) throw new Error("GLB JSON or binary chunk is missing");
    if (String(document.asset?.version)!=="2.0") throw new Error("only glTF 2.0 is supported");
    return {buffer,view,document,binaryStart,sourceUrl};
  }

  function readComponent(view, offset, type) {
    if (type===5120) return view.getInt8(offset); if (type===5121) return view.getUint8(offset);
    if (type===5122) return view.getInt16(offset,true); if (type===5123) return view.getUint16(offset,true);
    if (type===5125) return view.getUint32(offset,true); if (type===5126) return view.getFloat32(offset,true);
    throw new Error(`unsupported accessor component type ${type}`);
  }

  function normalizedComponent(value,type) {
    if (type===5120) return Math.max(value/127,-1); if (type===5121) return value/255;
    if (type===5122) return Math.max(value/32767,-1); if (type===5123) return value/65535;
    if (type===5125) return value/4294967295; return value;
  }

  function readAccessor(parsed,index,expected=null) {
    const a=parsed.document.accessors?.[index]; if (!a) throw new Error(`missing accessor ${index}`);
    if (a.sparse) throw new Error("sparse accessors are not supported yet");
    const bv=parsed.document.bufferViews?.[a.bufferView]; if (!bv || bv.buffer!==0) throw new Error("renderer expects embedded GLB buffer 0");
    const components=COMPONENTS[a.type], bytes=COMPONENT_BYTES[a.componentType];
    if (!components || !bytes || (expected && components!==expected)) throw new Error("unsupported accessor layout");
    const stride=bv.byteStride||bytes*components, start=parsed.binaryStart+(bv.byteOffset||0)+(a.byteOffset||0), out=new Float32Array(a.count*components);
    for (let i=0;i<a.count;i+=1) for (let c=0;c<components;c+=1) {
      const raw=readComponent(parsed.view,start+i*stride+c*bytes,a.componentType);
      out[i*components+c]=a.normalized?normalizedComponent(raw,a.componentType):raw;
    }
    return out;
  }

  function readIndices(parsed,index,vertexCount) {
    if (index===undefined || index===null) { const out=vertexCount<65535?new Uint16Array(vertexCount):new Uint32Array(vertexCount); for(let i=0;i<vertexCount;i+=1) out[i]=i; return out; }
    const a=parsed.document.accessors?.[index], bv=parsed.document.bufferViews?.[a?.bufferView];
    if (!a || a.type!=="SCALAR" || !bv || bv.buffer!==0 || ![5121,5123,5125].includes(a.componentType)) throw new Error("invalid index accessor");
    const bytes=COMPONENT_BYTES[a.componentType], stride=bv.byteStride||bytes, start=parsed.binaryStart+(bv.byteOffset||0)+(a.byteOffset||0), values=new Uint32Array(a.count); let max=0;
    for(let i=0;i<a.count;i+=1){values[i]=readComponent(parsed.view,start+i*stride,a.componentType);max=Math.max(max,values[i]);}
    return max<65535?new Uint16Array(values):values;
  }

  function bounds(parsed,index,positions) {
    const a=parsed.document.accessors?.[index]||{}; if(Array.isArray(a.min)&&Array.isArray(a.max)) return {min:a.min.slice(0,3),max:a.max.slice(0,3)};
    const min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];
    for(let i=0;i<positions.length;i+=3) for(let c=0;c<3;c+=1){min[c]=Math.min(min[c],positions[i+c]);max[c]=Math.max(max[c],positions[i+c]);}
    return {min,max};
  }

  function expandBounds(target,local,m) {
    for(const x of [local.min[0],local.max[0]]) for(const y of [local.min[1],local.max[1]]) for(const z of [local.min[2],local.max[2]]) {
      const p=transformPoint(m,[x,y,z]); for(let i=0;i<3;i+=1){target.min[i]=Math.min(target.min[i],p[i]);target.max[i]=Math.max(target.max[i],p[i]);}
    }
  }

  const pickColor=(index)=>{const v=index+1;return[(v&255)/255,((v>>8)&255)/255,((v>>16)&255)/255];};
  const decodePick=(p)=>{const v=p[0]+(p[1]<<8)+(p[2]<<16);return v===0?-1:v-1;};

  class BakeSmartProfessionalRenderer {
    constructor(canvas, options={}) {
      this.canvas=canvas;
      this.gl=canvas.getContext("webgl2",{antialias:true,alpha:true,premultipliedAlpha:false})||canvas.getContext("webgl",{antialias:true,alpha:true,premultipliedAlpha:false});
      if(!this.gl) throw new Error("WebGL is unavailable in this browser");
      this.isWebGl2=typeof WebGL2RenderingContext!=="undefined"&&this.gl instanceof WebGL2RenderingContext;
      this.uintExtension=this.isWebGl2?true:this.gl.getExtension("OES_element_index_uint");
      this.program=this._program(VS,FS); this.locations=this._locations(); this.whiteTexture=this._solidTexture([255,255,255,255]);
      this.modules=[];this.drawables=[];this.sceneBounds={min:[Infinity,Infinity,Infinity],max:[-Infinity,-Infinity,-Infinity]};
      this.sceneCenter=[0,1,0];this.sceneRadius=2;this.yaw=-0.42;this.pitch=-0.18;this.distance=5;this.pan=[0,0];this.selectedModuleIndex=-1;
      this.onSelection=typeof options.onSelection==="function"?options.onSelection:()=>{};this.activePointers=new Map();this.pointerMoved=false;this.lastPinch=null;this.controlsInstalled=false;
      this.gl.enable(this.gl.DEPTH_TEST);
    }

    _shader(type,source){const s=this.gl.createShader(type);this.gl.shaderSource(s,source);this.gl.compileShader(s);if(!this.gl.getShaderParameter(s,this.gl.COMPILE_STATUS)){const m=this.gl.getShaderInfoLog(s)||"shader compilation failed";this.gl.deleteShader(s);throw new Error(m);}return s;}
    _program(vs,fs){const v=this._shader(this.gl.VERTEX_SHADER,vs),f=this._shader(this.gl.FRAGMENT_SHADER,fs),p=this.gl.createProgram();this.gl.attachShader(p,v);this.gl.attachShader(p,f);this.gl.linkProgram(p);this.gl.deleteShader(v);this.gl.deleteShader(f);if(!this.gl.getProgramParameter(p,this.gl.LINK_STATUS))throw new Error(this.gl.getProgramInfoLog(p)||"renderer link failed");return p;}
    _locations(){const g=this.gl,p=this.program,a=(n)=>g.getAttribLocation(p,n),u=(n)=>g.getUniformLocation(p,n);return{aPosition:a("aPosition"),aNormal:a("aNormal"),aColor:a("aColor"),aVertexMaterial:a("aVertexMaterial"),aUv:a("aUv"),uModel:u("uModel"),uViewProj:u("uViewProj"),uShadowPass:u("uShadowPass"),uPickPass:u("uPickPass"),uPickColor:u("uPickColor"),uSelected:u("uSelected"),uBaseColorFactor:u("uBaseColorFactor"),uMetallicFactor:u("uMetallicFactor"),uRoughnessFactor:u("uRoughnessFactor"),uEmissiveFactor:u("uEmissiveFactor"),uHasVertexMaterial:u("uHasVertexMaterial"),uHasBaseColorTexture:u("uHasBaseColorTexture"),uHasMetalRoughTexture:u("uHasMetalRoughTexture"),uHasEmissiveTexture:u("uHasEmissiveTexture"),uBaseColorTexture:u("uBaseColorTexture"),uMetalRoughTexture:u("uMetalRoughTexture"),uEmissiveTexture:u("uEmissiveTexture")};}
    _solidTexture(rgba){const t=this.gl.createTexture();this.gl.bindTexture(this.gl.TEXTURE_2D,t);this.gl.texImage2D(this.gl.TEXTURE_2D,0,this.gl.RGBA,1,1,0,this.gl.RGBA,this.gl.UNSIGNED_BYTE,new Uint8Array(rgba));this.gl.texParameteri(this.gl.TEXTURE_2D,this.gl.TEXTURE_MIN_FILTER,this.gl.LINEAR);this.gl.texParameteri(this.gl.TEXTURE_2D,this.gl.TEXTURE_MAG_FILTER,this.gl.LINEAR);return t;}
    _buffer(values){const b=this.gl.createBuffer();this.gl.bindBuffer(this.gl.ARRAY_BUFFER,b);this.gl.bufferData(this.gl.ARRAY_BUFFER,values,this.gl.STATIC_DRAW);return b;}
    _indexBuffer(values){if(values instanceof Uint32Array&&!this.uintExtension)throw new Error("This browser cannot draw 32-bit GLB indices; use a lower LOD asset");const b=this.gl.createBuffer();this.gl.bindBuffer(this.gl.ELEMENT_ARRAY_BUFFER,b);this.gl.bufferData(this.gl.ELEMENT_ARRAY_BUFFER,values,this.gl.STATIC_DRAW);return b;}

    async _texture(parsed,index,cache){if(index===undefined||index===null)return null;if(cache.has(index))return cache.get(index);const promise=(async()=>{const td=parsed.document.textures?.[index],im=parsed.document.images?.[td?.source];if(!td||!im)return null;let url=null,revoke=false;if(Number.isInteger(im.bufferView)){const bv=parsed.document.bufferViews?.[im.bufferView];if(!bv||bv.buffer!==0)throw new Error("embedded image must use GLB buffer 0");url=URL.createObjectURL(new Blob([new Uint8Array(parsed.buffer,parsed.binaryStart+(bv.byteOffset||0),bv.byteLength)],{type:im.mimeType||"application/octet-stream"}));revoke=true;}else if(typeof im.uri==="string"){if(im.uri.startsWith("data:"))url=im.uri;else{const resolved=new URL(im.uri,parsed.sourceUrl);if(resolved.origin!==window.location.origin)throw new Error("external texture image must be same-origin");url=resolved.href;}}if(!url)return null;const image=await new Promise((resolve,reject)=>{const e=new Image();e.onload=()=>resolve(e);e.onerror=()=>reject(new Error("GLB texture image could not be decoded"));e.src=url;});const t=this.gl.createTexture();this.gl.bindTexture(this.gl.TEXTURE_2D,t);this.gl.texImage2D(this.gl.TEXTURE_2D,0,this.gl.RGBA,this.gl.RGBA,this.gl.UNSIGNED_BYTE,image);this.gl.texParameteri(this.gl.TEXTURE_2D,this.gl.TEXTURE_MIN_FILTER,this.gl.LINEAR);this.gl.texParameteri(this.gl.TEXTURE_2D,this.gl.TEXTURE_MAG_FILTER,this.gl.LINEAR);this.gl.texParameteri(this.gl.TEXTURE_2D,this.gl.TEXTURE_WRAP_S,this.gl.CLAMP_TO_EDGE);this.gl.texParameteri(this.gl.TEXTURE_2D,this.gl.TEXTURE_WRAP_T,this.gl.CLAMP_TO_EDGE);if(revoke)URL.revokeObjectURL(url);return t;})();cache.set(index,promise);return promise;}

    async loadModule({url,id,label=id,translation:position=[0,0,0],uniformScale=1.0}){
      const response=await fetch(url,{cache:"no-store"});if(!response.ok)throw new Error(`${label}: GLB request returned ${response.status}`);
      const parsed=parseGlb(await response.arrayBuffer(),response.url||new URL(url,window.location.href).href),moduleIndex=this.modules.length,moduleBase=multiply(translation(...position),scaling(uniformScale,uniformScale,uniformScale));
      const module={id,label,url,moduleIndex,drawables:[],bounds:{min:[Infinity,Infinity,Infinity],max:[-Infinity,-Infinity,-Infinity]}},cache=new Map(),sceneIndex=Number.isInteger(parsed.document.scene)?parsed.document.scene:0,roots=parsed.document.scenes?.[sceneIndex]?.nodes||parsed.document.nodes?.map((_,i)=>i)||[];
      const visit=async(nodeIndex,parent)=>{const node=parsed.document.nodes?.[nodeIndex];if(!node)return;const world=multiply(parent,nodeMatrix(node));if(Number.isInteger(node.mesh)){for(const primitive of parsed.document.meshes?.[node.mesh]?.primitives||[]){if((primitive.mode??4)!==4)continue;const positions=readAccessor(parsed,primitive.attributes.POSITION,3),vertexCount=positions.length/3;let normals;if(primitive.attributes.NORMAL===undefined){normals=new Float32Array(vertexCount*3);for(let i=0;i<vertexCount;i+=1)normals[i*3+1]=1;}else normals=readAccessor(parsed,primitive.attributes.NORMAL,3);const rawColor=primitive.attributes.COLOR_0===undefined?null:readAccessor(parsed,primitive.attributes.COLOR_0),colors=new Float32Array(vertexCount*3);if(rawColor){const cc=rawColor.length/vertexCount;for(let i=0;i<vertexCount;i+=1){colors[i*3]=rawColor[i*cc];colors[i*3+1]=rawColor[i*cc+1];colors[i*3+2]=rawColor[i*cc+2];}}else colors.fill(1);const uv=primitive.attributes.TEXCOORD_0===undefined?new Float32Array(vertexCount*2):readAccessor(parsed,primitive.attributes.TEXCOORD_0,2),vm=primitive.attributes._MATERIAL===undefined?new Float32Array(vertexCount*3):readAccessor(parsed,primitive.attributes._MATERIAL,3),indices=readIndices(parsed,primitive.indices,vertexCount),md=parsed.document.materials?.[primitive.material]||{},pbr=md.pbrMetallicRoughness||{},modelMatrix=multiply(moduleBase,world),localBounds=bounds(parsed,primitive.attributes.POSITION,positions);expandBounds(module.bounds,localBounds,modelMatrix);expandBounds(this.sceneBounds,localBounds,modelMatrix);const material={baseColorFactor:pbr.baseColorFactor||[1,1,1,1],metallicFactor:pbr.metallicFactor??1,roughnessFactor:pbr.roughnessFactor??1,emissiveFactor:md.emissiveFactor||[0,0,0],baseTexture:await this._texture(parsed,pbr.baseColorTexture?.index,cache),metalRoughTexture:await this._texture(parsed,pbr.metallicRoughnessTexture?.index,cache),emissiveTexture:await this._texture(parsed,md.emissiveTexture?.index,cache)};const d={moduleIndex,modelMatrix,positionBuffer:this._buffer(positions),normalBuffer:this._buffer(normals),colorBuffer:this._buffer(colors),vertexMaterialBuffer:this._buffer(vm),uvBuffer:this._buffer(uv),indexBuffer:this._indexBuffer(indices),indexCount:indices.length,indexType:indices instanceof Uint32Array?this.gl.UNSIGNED_INT:this.gl.UNSIGNED_SHORT,vertexCount,triangleCount:Math.floor(indices.length/3),hasVertexMaterial:primitive.attributes._MATERIAL!==undefined,material};module.drawables.push(d);this.drawables.push(d);}}for(const child of node.children||[])await visit(child,world);};
      for(const root of roots)await visit(root,identity());if(!module.drawables.length)throw new Error(`${label}: no triangle mesh primitive was found`);this.modules.push(module);this._updateFrame();this.draw();return module;
    }

    _updateFrame(){if(!Number.isFinite(this.sceneBounds.min[0]))return;this.sceneCenter=this.sceneBounds.min.map((v,i)=>(v+this.sceneBounds.max[i])/2);const span=this.sceneBounds.min.map((v,i)=>this.sceneBounds.max[i]-v);this.sceneRadius=Math.max(Math.hypot(...span)/2,0.5);if(this.modules.length===1)this.distance=Math.max(this.sceneRadius*2.5,2.4);}
    resetView(){this.yaw=-0.42;this.pitch=-0.18;this.pan=[0,0];this.distance=Math.max(this.sceneRadius*2.5,2.4);this.draw();}
    stats(){return{moduleCount:this.modules.length,vertexCount:this.drawables.reduce((s,d)=>s+d.vertexCount,0),triangleCount:this.drawables.reduce((s,d)=>s+d.triangleCount,0)};}
    _viewProjection(){const target=[this.sceneCenter[0]+this.pan[0],this.sceneCenter[1]+this.pan[1],this.sceneCenter[2]],cp=Math.cos(this.pitch),eye=[target[0]+this.distance*cp*Math.sin(this.yaw),target[1]+this.distance*Math.sin(this.pitch),target[2]+this.distance*cp*Math.cos(this.yaw)];return multiply(perspective(Math.PI/4.4,this.canvas.width/Math.max(this.canvas.height,1),0.01,Math.max(100,this.distance*20)),lookAt(eye,target,[0,1,0]));}
    _attr(loc,buffer,components,fallback){if(loc<0)return;if(buffer){this.gl.bindBuffer(this.gl.ARRAY_BUFFER,buffer);this.gl.enableVertexAttribArray(loc);this.gl.vertexAttribPointer(loc,components,this.gl.FLOAT,false,0,0);}else{this.gl.disableVertexAttribArray(loc);components===2?this.gl.vertexAttrib2f(loc,...fallback):this.gl.vertexAttrib3f(loc,...fallback);}}
    _bindTexture(unit,texture,sampler){this.gl.activeTexture(this.gl.TEXTURE0+unit);this.gl.bindTexture(this.gl.TEXTURE_2D,texture||this.whiteTexture);this.gl.uniform1i(sampler,unit);}
    _draw(d,vp,{pickPass=false,shadowPass=false}={}){const g=this.gl,l=this.locations,m=d.material;this._attr(l.aPosition,d.positionBuffer,3,[0,0,0]);this._attr(l.aNormal,d.normalBuffer,3,[0,1,0]);this._attr(l.aColor,d.colorBuffer,3,[1,1,1]);this._attr(l.aVertexMaterial,d.vertexMaterialBuffer,3,[0,0.78,0]);this._attr(l.aUv,d.uvBuffer,2,[0,0]);g.bindBuffer(g.ELEMENT_ARRAY_BUFFER,d.indexBuffer);g.uniformMatrix4fv(l.uModel,false,d.modelMatrix);g.uniformMatrix4fv(l.uViewProj,false,vp);g.uniform1f(l.uShadowPass,shadowPass?1:0);g.uniform1f(l.uPickPass,pickPass?1:0);g.uniform3fv(l.uPickColor,pickColor(d.moduleIndex));g.uniform1f(l.uSelected,d.moduleIndex===this.selectedModuleIndex?1:0);g.uniform1f(l.uHasVertexMaterial,d.hasVertexMaterial?1:0);g.uniform4fv(l.uBaseColorFactor,m.baseColorFactor);g.uniform1f(l.uMetallicFactor,m.metallicFactor);g.uniform1f(l.uRoughnessFactor,m.roughnessFactor);g.uniform3fv(l.uEmissiveFactor,m.emissiveFactor);g.uniform1f(l.uHasBaseColorTexture,m.baseTexture?1:0);g.uniform1f(l.uHasMetalRoughTexture,m.metalRoughTexture?1:0);g.uniform1f(l.uHasEmissiveTexture,m.emissiveTexture?1:0);this._bindTexture(0,m.baseTexture,l.uBaseColorTexture);this._bindTexture(1,m.metalRoughTexture,l.uMetalRoughTexture);this._bindTexture(2,m.emissiveTexture,l.uEmissiveTexture);g.drawElements(g.TRIANGLES,d.indexCount,d.indexType,0);}
    resize(){const ratio=Math.min(window.devicePixelRatio||1,2),w=Math.max(1,Math.floor(this.canvas.clientWidth*ratio)),h=Math.max(1,Math.floor(this.canvas.clientHeight*ratio));if(this.canvas.width!==w||this.canvas.height!==h){this.canvas.width=w;this.canvas.height=h;}}
    draw(){const g=this.gl;this.resize();g.viewport(0,0,this.canvas.width,this.canvas.height);g.clearColor(0,0,0,0);g.clear(g.COLOR_BUFFER_BIT|g.DEPTH_BUFFER_BIT);if(!this.drawables.length)return;g.useProgram(this.program);const vp=this._viewProjection();g.disable(g.BLEND);g.depthMask(true);for(const d of this.drawables)this._draw(d,vp);g.enable(g.BLEND);g.blendFunc(g.SRC_ALPHA,g.ONE_MINUS_SRC_ALPHA);g.depthMask(false);for(const d of this.drawables)this._draw(d,vp,{shadowPass:true});g.depthMask(true);g.disable(g.BLEND);}
    pick(clientX,clientY){if(!this.drawables.length)return null;const rect=this.canvas.getBoundingClientRect(),x=Math.floor((clientX-rect.left)*this.canvas.width/Math.max(rect.width,1)),y=Math.floor((rect.bottom-clientY)*this.canvas.height/Math.max(rect.height,1));if(x<0||y<0||x>=this.canvas.width||y>=this.canvas.height)return null;const g=this.gl;g.viewport(0,0,this.canvas.width,this.canvas.height);g.clearColor(0,0,0,1);g.clear(g.COLOR_BUFFER_BIT|g.DEPTH_BUFFER_BIT);g.useProgram(this.program);g.disable(g.BLEND);const vp=this._viewProjection();for(const d of this.drawables)this._draw(d,vp,{pickPass:true});const pixel=new Uint8Array(4);g.readPixels(x,y,1,1,g.RGBA,g.UNSIGNED_BYTE,pixel);const i=decodePick(pixel);this.selectedModuleIndex=i>=0&&i<this.modules.length?i:-1;const selected=this.selectedModuleIndex>=0?this.modules[this.selectedModuleIndex]:null;this.onSelection(selected);this.draw();return selected;}
    installControls(){if(this.controlsInstalled)return;this.controlsInstalled=true;const c=this.canvas;let previous=null;c.addEventListener("pointerdown",(e)=>{c.setPointerCapture(e.pointerId);this.activePointers.set(e.pointerId,{x:e.clientX,y:e.clientY});previous={x:e.clientX,y:e.clientY};this.pointerMoved=false;if(this.activePointers.size===2){const v=[...this.activePointers.values()];this.lastPinch=Math.hypot(v[0].x-v[1].x,v[0].y-v[1].y);}});c.addEventListener("pointermove",(e)=>{if(!this.activePointers.has(e.pointerId))return;const old=this.activePointers.get(e.pointerId);this.activePointers.set(e.pointerId,{x:e.clientX,y:e.clientY});if(this.activePointers.size===2){const v=[...this.activePointers.values()],dist=Math.hypot(v[0].x-v[1].x,v[0].y-v[1].y);if(this.lastPinch&&dist>0){this.distance=clamp(this.distance*this.lastPinch/dist,this.sceneRadius*0.6,this.sceneRadius*12+4);this.pointerMoved=true;this.draw();}this.lastPinch=dist;return;}const dx=e.clientX-old.x,dy=e.clientY-old.y;if(Math.abs(dx)+Math.abs(dy)>1)this.pointerMoved=true;if(e.shiftKey||e.button===1||e.buttons===4){const scale=this.distance*0.0018;this.pan[0]-=dx*scale;this.pan[1]+=dy*scale;}else{this.yaw+=dx*0.008;this.pitch=clamp(this.pitch+dy*0.006,-1.35,1.25);}previous={x:e.clientX,y:e.clientY};this.draw();});const finish=(e)=>{if(this.activePointers.has(e.pointerId))this.activePointers.delete(e.pointerId);this.lastPinch=null;if(!this.pointerMoved&&previous)this.pick(e.clientX,e.clientY);previous=null;};c.addEventListener("pointerup",finish);c.addEventListener("pointercancel",finish);c.addEventListener("wheel",(e)=>{e.preventDefault();this.distance=clamp(this.distance*Math.exp(e.deltaY*0.001),this.sceneRadius*0.6,this.sceneRadius*12+4);this.draw();},{passive:false});window.addEventListener("resize",()=>this.draw());}
  }

  window.BakeSmartProfessionalRenderer = BakeSmartProfessionalRenderer;
})();
