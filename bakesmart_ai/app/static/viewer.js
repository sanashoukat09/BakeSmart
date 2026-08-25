(() => {
  "use strict";

  const canvas = document.getElementById("scene-canvas");
  const statusCard = document.getElementById("loading-card");
  const statusText = document.getElementById("status-text");
  const resetButton = document.getElementById("reset-view");
  const downloadLink = document.getElementById("download-glb");
  const designId = window.location.pathname.split("/").filter(Boolean).pop();

  if (!/^design-[0-9a-f]{20}$/.test(designId || "")) {
    showError("This BakeSmart scene link is invalid.");
    return;
  }

  const glbUrl = `/api/v1/designs/${encodeURIComponent(designId)}/scene.glb`;
  downloadLink.href = glbUrl;
  downloadLink.download = `${designId}.glb`;

  const gl = canvas.getContext("webgl", {
    antialias: true,
    alpha: true,
    premultipliedAlpha: false,
    preserveDrawingBuffer: false,
  });
  if (!gl) {
    showError("Interactive 3D is unavailable in this browser. Concept preview—not to scale.");
    return;
  }

  let program;
  let geometry;
  let yaw = -0.38;
  let pitch = -0.2;
  let cameraDistance = 3.9;
  let pointerX = 0;
  let pointerY = 0;
  let pinchDistance = null;
  const activePointers = new Map();

  const vertexShaderSource = `
    precision mediump float;
    attribute vec3 aPosition;
    attribute vec3 aNormal;
    attribute vec3 aColor;
    uniform mat4 uMvp;
    uniform mat4 uModel;
    uniform float uShadowPass;
    varying vec3 vNormal;
    varying vec3 vColor;
    varying float vHeight;
    void main() {
      vec3 position = aPosition;
      vHeight = aPosition.y;
      if (uShadowPass > 0.5) {
        float heightAboveFloor = max(aPosition.y, 0.0);
        position.x += heightAboveFloor * 0.16;
        position.z += heightAboveFloor * 0.11;
        position.y = 0.006;
      }
      vNormal = normalize(mat3(uModel) * aNormal);
      vColor = aColor;
      gl_Position = uMvp * vec4(position, 1.0);
    }
  `;

  const fragmentShaderSource = `
    precision mediump float;
    varying vec3 vNormal;
    varying vec3 vColor;
    varying float vHeight;
    uniform float uShadowPass;

    void main() {
      if (uShadowPass > 0.5) {
        if (vHeight < 0.045) {
          discard;
        }
        float shadowStrength = clamp(0.19 + vHeight * 0.025, 0.19, 0.28);
        gl_FragColor = vec4(0.18, 0.12, 0.14, shadowStrength);
        return;
      }

      vec3 normal = normalize(vNormal);
      vec3 keyLight = normalize(vec3(0.42, 0.86, 0.34));
      vec3 fillLight = normalize(vec3(-0.58, 0.34, 0.72));
      vec3 viewDirection = normalize(vec3(0.0, 0.22, 1.0));

      float keyDiffuse = max(dot(normal, keyLight), 0.0);
      float fillDiffuse = max(dot(normal, fillLight), 0.0);
      float hemisphere = normal.y * 0.5 + 0.5;

      float luminance = dot(vColor, vec3(0.2126, 0.7152, 0.0722));
      vec3 baseColor = clamp(mix(vec3(luminance), vColor, 1.14), 0.0, 1.0);

      vec3 halfVector = normalize(keyLight + viewDirection);
      float specular = pow(max(dot(normal, halfVector), 0.0), 30.0) * 0.14;
      float edgeLight = pow(1.0 - max(dot(normal, viewDirection), 0.0), 3.0) * 0.055;
      float heightFactor = 1.0 - exp(-max(vHeight, 0.0) * 2.6);
      float ambientOcclusion = mix(0.8, 1.0, heightFactor);

      vec3 warmKey = vec3(1.06, 0.97, 0.9) * keyDiffuse * 0.78;
      vec3 coolFill = vec3(0.84, 0.91, 1.0) * fillDiffuse * 0.24;
      vec3 ambient = mix(vec3(0.31, 0.3, 0.33), vec3(0.5, 0.47, 0.46), hemisphere);
      vec3 shaded = baseColor * (ambient + warmKey + coolFill) * ambientOcclusion;
      shaded += vec3(1.0, 0.91, 0.78) * specular;
      shaded += baseColor * edgeLight;

      shaded = pow(clamp(shaded, 0.0, 1.0), vec3(0.86));
      gl_FragColor = vec4(shaded, 1.0);
    }
  `;

  try {
    program = createProgram(vertexShaderSource, fragmentShaderSource);
  } catch (error) {
    showError(`The 3D renderer could not start: ${error.message}`);
    return;
  }

  fetch(glbUrl, { cache: "no-store" })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`scene request returned ${response.status}`);
      }
      return response.arrayBuffer();
    })
    .then((buffer) => {
      geometry = uploadGeometry(parseGlb(buffer));
      statusCard.classList.add("ready");
      statusText.textContent =
        `Interactive 3D ready • ${geometry.vertexCount.toLocaleString()} vertices • ` +
        `${geometry.triangleCount.toLocaleString()} triangles`;
      resizeAndDraw();
    })
    .catch((error) => {
      showError(
        `The 3D scene could not be opened. Concept preview—not to scale. ${error.message}`,
      );
    });

  function showError(message) {
    statusCard.classList.add("error");
    statusText.textContent = message;
  }

  function createShader(type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      const detail = gl.getShaderInfoLog(shader);
      gl.deleteShader(shader);
      throw new Error(detail || "shader compilation failed");
    }
    return shader;
  }

  function createProgram(vertexSource, fragmentSource) {
    const vertexShader = createShader(gl.VERTEX_SHADER, vertexSource);
    const fragmentShader = createShader(gl.FRAGMENT_SHADER, fragmentSource);
    const linkedProgram = gl.createProgram();
    gl.attachShader(linkedProgram, vertexShader);
    gl.attachShader(linkedProgram, fragmentShader);
    gl.linkProgram(linkedProgram);
    gl.deleteShader(vertexShader);
    gl.deleteShader(fragmentShader);
    if (!gl.getProgramParameter(linkedProgram, gl.LINK_STATUS)) {
      const detail = gl.getProgramInfoLog(linkedProgram);
      gl.deleteProgram(linkedProgram);
      throw new Error(detail || "shader linking failed");
    }
    return linkedProgram;
  }

  function parseGlb(buffer) {
    const view = new DataView(buffer);
    if (view.byteLength < 20 || view.getUint32(0, true) !== 0x46546c67) {
      throw new Error("invalid GLB header");
    }
    if (view.getUint32(4, true) !== 2 || view.getUint32(8, true) !== view.byteLength) {
      throw new Error("unsupported GLB version or length");
    }

    let offset = 12;
    let document;
    let binaryStart = -1;
    while (offset + 8 <= view.byteLength) {
      const chunkLength = view.getUint32(offset, true);
      const chunkType = view.getUint32(offset + 4, true);
      const chunkStart = offset + 8;
      if (chunkStart + chunkLength > view.byteLength) {
        throw new Error("GLB chunk exceeds file length");
      }
      if (chunkType === 0x4e4f534a) {
        const jsonBytes = new Uint8Array(buffer, chunkStart, chunkLength);
        document = JSON.parse(new TextDecoder().decode(jsonBytes).trim());
      } else if (chunkType === 0x004e4942) {
        binaryStart = chunkStart;
      }
      offset = chunkStart + chunkLength;
    }
    if (!document || binaryStart < 0) {
      throw new Error("GLB JSON or binary chunk is missing");
    }

    const primitive = document.meshes?.[0]?.primitives?.[0];
    if (!primitive) {
      throw new Error("GLB mesh primitive is missing");
    }
    return {
      positions: readAccessor(primitive.attributes.POSITION),
      normals: readAccessor(primitive.attributes.NORMAL),
      colors: readAccessor(primitive.attributes.COLOR_0),
      indices: readAccessor(primitive.indices),
      boundsMin: document.accessors[primitive.attributes.POSITION].min,
      boundsMax: document.accessors[primitive.attributes.POSITION].max,
    };

    function readAccessor(accessorIndex) {
      const accessor = document.accessors[accessorIndex];
      const bufferView = document.bufferViews[accessor.bufferView];
      const components = {
        SCALAR: 1,
        VEC2: 2,
        VEC3: 3,
        VEC4: 4,
      }[accessor.type];
      const constructors = {
        5123: Uint16Array,
        5125: Uint32Array,
        5126: Float32Array,
      };
      const Constructor = constructors[accessor.componentType];
      if (!components || !Constructor) {
        throw new Error("GLB accessor type is unsupported by this viewer");
      }
      const byteOffset =
        binaryStart +
        (bufferView.byteOffset || 0) +
        (accessor.byteOffset || 0);
      return new Constructor(buffer, byteOffset, accessor.count * components);
    }
  }

  function uploadGeometry(parsed) {
    gl.useProgram(program);
    bindAttribute("aPosition", parsed.positions);
    bindAttribute("aNormal", parsed.normals);
    bindAttribute("aColor", parsed.colors);

    const indexBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, indexBuffer);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, parsed.indices, gl.STATIC_DRAW);
    return {
      indexBuffer,
      indexCount: parsed.indices.length,
      indexType: parsed.indices instanceof Uint32Array ? gl.UNSIGNED_INT : gl.UNSIGNED_SHORT,
      vertexCount: parsed.positions.length / 3,
      triangleCount: parsed.indices.length / 3,
      boundsMin: parsed.boundsMin,
      boundsMax: parsed.boundsMax,
    };
  }

  function bindAttribute(name, values) {
    const location = gl.getAttribLocation(program, name);
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, values, gl.STATIC_DRAW);
    gl.enableVertexAttribArray(location);
    gl.vertexAttribPointer(location, 3, gl.FLOAT, false, 0, 0);
  }

  function draw() {
    if (!geometry) {
      return;
    }
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.enable(gl.DEPTH_TEST);
    gl.disable(gl.CULL_FACE);
    gl.clearColor(0.0, 0.0, 0.0, 0.0);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.useProgram(program);

    const center = geometry.boundsMin.map(
      (minimum, index) => (minimum + geometry.boundsMax[index]) / 2,
    );
    const span = geometry.boundsMin.map(
      (minimum, index) => geometry.boundsMax[index] - minimum,
    );
    const normalization = 3.05 / Math.max(...span, 0.01);
    const centerTranslation = translation(-center[0], -center[1], -center[2]);
    const rotation = multiply(rotationY(yaw), rotationX(pitch));
    const model = multiply(scale(normalization), multiply(rotation, centerTranslation));
    const view = translation(0, -0.03, -cameraDistance);
    const projection = perspective(
      Math.PI / 5.2,
      canvas.width / Math.max(canvas.height, 1),
      0.01,
      100,
    );
    const mvp = multiply(projection, multiply(view, model));
    const mvpLocation = gl.getUniformLocation(program, "uMvp");
    const modelLocation = gl.getUniformLocation(program, "uModel");
    const shadowLocation = gl.getUniformLocation(program, "uShadowPass");

    gl.uniformMatrix4fv(mvpLocation, false, mvp);
    gl.uniformMatrix4fv(modelLocation, false, model);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, geometry.indexBuffer);

    gl.uniform1f(shadowLocation, 0.0);
    gl.disable(gl.BLEND);
    gl.depthMask(true);
    gl.drawElements(gl.TRIANGLES, geometry.indexCount, geometry.indexType, 0);

    gl.uniform1f(shadowLocation, 1.0);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.depthMask(false);
    gl.drawElements(gl.TRIANGLES, geometry.indexCount, geometry.indexType, 0);
    gl.depthMask(true);
    gl.disable(gl.BLEND);
  }

  function resizeAndDraw() {
    const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.floor(canvas.clientWidth * pixelRatio));
    const height = Math.max(1, Math.floor(canvas.clientHeight * pixelRatio));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    draw();
  }

  function identity() {
    return new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]);
  }

  function multiply(left, right) {
    const output = new Float32Array(16);
    for (let column = 0; column < 4; column += 1) {
      for (let row = 0; row < 4; row += 1) {
        let value = 0;
        for (let index = 0; index < 4; index += 1) {
          value += left[index * 4 + row] * right[column * 4 + index];
        }
        output[column * 4 + row] = value;
      }
    }
    return output;
  }

  function translation(x, y, z) {
    const output = identity();
    output[12] = x;
    output[13] = y;
    output[14] = z;
    return output;
  }

  function scale(value) {
    const output = identity();
    output[0] = value;
    output[5] = value;
    output[10] = value;
    return output;
  }

  function rotationX(angle) {
    const output = identity();
    const cosine = Math.cos(angle);
    const sine = Math.sin(angle);
    output[5] = cosine;
    output[6] = sine;
    output[9] = -sine;
    output[10] = cosine;
    return output;
  }

  function rotationY(angle) {
    const output = identity();
    const cosine = Math.cos(angle);
    const sine = Math.sin(angle);
    output[0] = cosine;
    output[2] = -sine;
    output[8] = sine;
    output[10] = cosine;
    return output;
  }

  function perspective(fieldOfView, aspect, near, far) {
    const output = new Float32Array(16);
    const focalLength = 1 / Math.tan(fieldOfView / 2);
    output[0] = focalLength / aspect;
    output[5] = focalLength;
    output[10] = (far + near) / (near - far);
    output[11] = -1;
    output[14] = (2 * far * near) / (near - far);
    return output;
  }

  canvas.addEventListener("pointerdown", (event) => {
    activePointers.set(event.pointerId, {
      x: event.clientX,
      y: event.clientY,
    });
    if (activePointers.size === 1) {
      pointerX = event.clientX;
      pointerY = event.clientY;
    } else if (activePointers.size === 2) {
      pinchDistance = distanceBetweenPointers();
    }
    canvas.setPointerCapture(event.pointerId);
  });

  canvas.addEventListener("pointermove", (event) => {
    if (!activePointers.has(event.pointerId)) {
      return;
    }
    activePointers.set(event.pointerId, {
      x: event.clientX,
      y: event.clientY,
    });
    if (activePointers.size >= 2) {
      const nextDistance = distanceBetweenPointers();
      if (pinchDistance && nextDistance > 0) {
        cameraDistance = Math.max(
          2.0,
          Math.min(8.0, cameraDistance * (pinchDistance / nextDistance)),
        );
      }
      pinchDistance = nextDistance;
      draw();
      return;
    }
    yaw += (event.clientX - pointerX) * 0.009;
    pitch = Math.max(-1.05, Math.min(1.05, pitch + (event.clientY - pointerY) * 0.009));
    pointerX = event.clientX;
    pointerY = event.clientY;
    draw();
  });

  const stopDragging = (event) => {
    activePointers.delete(event.pointerId);
    pinchDistance = null;
    if (activePointers.size === 1) {
      const remaining = activePointers.values().next().value;
      pointerX = remaining.x;
      pointerY = remaining.y;
    }
    if (canvas.hasPointerCapture(event.pointerId)) {
      canvas.releasePointerCapture(event.pointerId);
    }
  };
  canvas.addEventListener("pointerup", stopDragging);
  canvas.addEventListener("pointercancel", stopDragging);

  function distanceBetweenPointers() {
    const pointers = Array.from(activePointers.values()).slice(0, 2);
    if (pointers.length < 2) {
      return 0;
    }
    return Math.hypot(
      pointers[0].x - pointers[1].x,
      pointers[0].y - pointers[1].y,
    );
  }

  canvas.addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      cameraDistance = Math.max(2.0, Math.min(8.0, cameraDistance + event.deltaY * 0.004));
      draw();
    },
    { passive: false },
  );

  resetButton.addEventListener("click", () => {
    yaw = -0.38;
    pitch = -0.2;
    cameraDistance = 3.9;
    draw();
  });

  window.addEventListener("resize", resizeAndDraw);
  if (window.ResizeObserver) {
    new ResizeObserver(resizeAndDraw).observe(canvas);
  }
})();
