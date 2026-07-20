var JASSUB = (() => {
  var __create = Object.create;
  var __defProp = Object.defineProperty;
  var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __getProtoOf = Object.getPrototypeOf;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
  var __commonJS = (cb, mod) => function __require() {
    try {
      return mod || (0, cb[__getOwnPropNames(cb)[0]])((mod = { exports: {} }).exports, mod), mod.exports;
    } catch (e) {
      throw mod = 0, e;
    }
  };
  var __export = (target, all) => {
    for (var name in all)
      __defProp(target, name, { get: all[name], enumerable: true });
  };
  var __copyProps = (to, from, except, desc) => {
    if (from && typeof from === "object" || typeof from === "function") {
      for (let key of __getOwnPropNames(from))
        if (!__hasOwnProp.call(to, key) && key !== except)
          __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
    }
    return to;
  };
  var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
    // If the importer is in node compatibility mode or this is not an ESM
    // file that has been converted to a CommonJS file using a Babel-
    // compatible transform (i.e. "__esModule" has not been set), then set
    // "default" to the CommonJS "module.exports" for node compatibility.
    isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
    mod
  ));
  var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);
  var __publicField = (obj, key, value) => __defNormalProp(obj, typeof key !== "symbol" ? key + "" : key, value);

  // node_modules/throughput/index.js
  var require_throughput = __commonJS({
    "node_modules/throughput/index.js"(exports, module) {
      var hrtime = typeof process !== "undefined" && !!process.hrtime;
      var maxTick = 65535;
      var resolution = 10;
      var timeDiff = hrtime ? 1e9 / resolution : 1e3 / resolution;
      var now = hrtime ? () => {
        const [seconds, nanoseconds] = process.hrtime();
        return seconds * 1e9 + nanoseconds;
      } : () => performance.now();
      function getTick(start) {
        return (now() - start) / timeDiff & maxTick;
      }
      module.exports = function(seconds) {
        const start = now();
        const size = resolution * (seconds || 5);
        const buffer2 = [0];
        let pointer = 1;
        let last = getTick(start) - 1 & maxTick;
        return function(delta) {
          const tick = getTick(start);
          let dist = tick - last & maxTick;
          if (dist > size) dist = size;
          last = tick;
          while (dist--) {
            if (pointer === size) pointer = 0;
            buffer2[pointer] = buffer2[pointer === 0 ? size - 1 : pointer - 1];
            pointer++;
          }
          if (delta) buffer2[pointer - 1] += delta;
          const top = buffer2[pointer - 1];
          const btm = buffer2.length < size ? 0 : buffer2[pointer === size ? 0 : pointer];
          return buffer2.length < resolution ? top : (top - btm) * resolution / buffer2.length;
        };
      };
    }
  });

  // node_modules/jassub/src/jassub.ts
  var jassub_exports = {};
  __export(jassub_exports, {
    default: () => JASSUB
  });

  // node_modules/rvfc-polyfill/index.js
  var VidProto = typeof HTMLVideoElement !== "undefined" ? HTMLVideoElement.prototype : {};
  var hasQuality = "getVideoPlaybackQuality" in VidProto || "webkitDecodedFrameCount" in VidProto || "mozPresentedFrames" in VidProto || "mozPaintedFrames" in VidProto;
  if (!("requestVideoFrameCallback" in VidProto) && hasQuality && typeof requestAnimationFrame === "function") {
    VidProto._rvfcpolyfillmap = {};
    const getPlaybackQuality = "getVideoPlaybackQuality" in VidProto ? (video) => {
      const { totalFrameDelay, totalVideoFrames, droppedVideoFrames } = video.getVideoPlaybackQuality();
      return {
        presentedFrames: totalVideoFrames - droppedVideoFrames,
        totalFrameDelay
      };
    } : (video) => {
      return {
        presentedFrames: video.mozPresentedFrames || video.mozPaintedFrames || video.webkitDecodedFrameCount - (video.webkitDroppedFrameCount || 0),
        totalFrameDelay: video.mozFrameDelay || 0
      };
    };
    VidProto.requestVideoFrameCallback = function(callback) {
      const handle = performance.now();
      const quality = getPlaybackQuality(this);
      const baseline = quality.presentedFrames;
      const check = (old, now) => {
        const newquality = getPlaybackQuality(this);
        const presentedFrames = newquality.presentedFrames;
        if (presentedFrames > baseline) {
          const processingDuration = newquality.totalFrameDelay - quality.totalFrameDelay || 0;
          const timediff = now - old;
          callback(now, {
            presentationTime: now + processingDuration * 1e3,
            expectedDisplayTime: now + timediff,
            width: this.videoWidth,
            height: this.videoHeight,
            mediaTime: Math.max(0, this.currentTime || 0) + timediff / 1e3,
            presentedFrames,
            processingDuration
          });
          delete this._rvfcpolyfillmap[handle];
        } else {
          this._rvfcpolyfillmap[handle] = requestAnimationFrame((newer) => check(now, newer));
        }
      };
      this._rvfcpolyfillmap[handle] = requestAnimationFrame((newer) => check(handle, newer));
      return handle;
    };
    VidProto.cancelVideoFrameCallback = function(handle) {
      cancelAnimationFrame(this._rvfcpolyfillmap[handle]);
      delete this._rvfcpolyfillmap[handle];
    };
  }

  // node_modules/abslink/src/types.js
  var WireValueType = {
    RAW: "RAW",
    PROXY: "PROXY",
    THROW: "THROW",
    HANDLER: "HANDLER"
  };
  var MessageType = {
    GET: "GET",
    SET: "SET",
    APPLY: "APPLY",
    CONSTRUCT: "CONSTRUCT",
    RELEASE: "RELEASE"
  };

  // node_modules/abslink/src/abslink.js
  var proxyMarker = /* @__PURE__ */ Symbol("Abslink.proxy");
  var releaseProxy = /* @__PURE__ */ Symbol("Abslink.releaseProxy");
  var finalizer = /* @__PURE__ */ Symbol("Abslink.finalizer");
  var throwMarker = /* @__PURE__ */ Symbol("Abslink.thrown");
  var isObject = (val) => typeof val === "object" && val !== null || typeof val === "function";
  var proxyTransferHandler = {
    canHandle: (val) => isObject(val) && proxyMarker in val,
    serialize(obj, ep) {
      const markerID = obj[proxyMarker];
      expose(obj, ep, markerID);
      return [markerID, []];
    },
    deserialize(markerID, ep) {
      return wrap(ep, markerID);
    }
  };
  var throwTransferHandler = {
    canHandle: (value) => isObject(value) && throwMarker in value,
    serialize({ value }) {
      let serialized;
      if (value instanceof Error) {
        serialized = {
          isError: true,
          value: {
            message: value.message,
            name: value.name,
            stack: value.stack
          }
        };
      } else {
        serialized = { isError: false, value };
      }
      return [serialized, []];
    },
    deserialize(serialized) {
      if (serialized.isError) {
        throw Object.assign(new Error(serialized.value.message), serialized.value);
      }
      throw serialized.value;
    }
  };
  var transferHandlers = /* @__PURE__ */ new Map([
    ["proxy", proxyTransferHandler],
    ["throw", throwTransferHandler]
  ]);
  function filterPath(path, obj) {
    let parent = obj;
    const parentPath = path.slice(0, -1);
    for (const segment of parentPath) {
      if (Object.prototype.hasOwnProperty.call(parent, segment)) {
        parent = parent[segment];
      }
    }
    const lastSegment = path[path.length - 1];
    const RawValue = lastSegment ? parent[lastSegment] : parent;
    return { parent, RawValue, lastSegment };
  }
  function expose(obj, ep, rootMarkerID) {
    ep.on("message", function callback(data) {
      if (!data)
        return;
      const { id, type, path, markerID } = {
        path: [],
        ...data
      };
      if (markerID !== rootMarkerID)
        return;
      const argumentList = (data.argumentList ?? []).map((v) => fromWireValue(v, ep));
      let returnValue;
      try {
        const { parent, RawValue, lastSegment } = filterPath(path, obj);
        switch (type) {
          case MessageType.GET:
            returnValue = RawValue;
            break;
          case MessageType.SET:
            parent[lastSegment] = fromWireValue(data.value, ep);
            returnValue = true;
            break;
          case MessageType.APPLY:
            returnValue = RawValue.apply(parent, argumentList);
            break;
          case MessageType.CONSTRUCT:
            returnValue = new RawValue(...argumentList);
            break;
          case MessageType.RELEASE:
            returnValue = void 0;
            break;
          default:
            return;
        }
      } catch (value) {
        returnValue = { value, [throwMarker]: 0 };
      }
      Promise.resolve(returnValue).catch((value) => {
        return { value, [throwMarker]: 0 };
      }).then((returnValue2) => {
        if (type === MessageType.CONSTRUCT)
          returnValue2 = proxy(returnValue2);
        const [wireValue, transfer] = toWireValue(returnValue2, ep);
        ep.postMessage({ ...wireValue, id, markerID: rootMarkerID }, transfer);
        if (type === MessageType.RELEASE) {
          ep.off("message", callback);
          obj[finalizer]?.();
          ep.close?.();
        }
      }).catch((_) => {
        const [wireValue, transfer] = toWireValue({
          value: new TypeError("Unserializable return value"),
          [throwMarker]: 0
        }, ep);
        ep.postMessage({ ...wireValue, id, markerID: rootMarkerID }, transfer);
      });
    });
    return obj;
  }
  function wrap(endpoint, rootMarkerID) {
    const pendingListeners = /* @__PURE__ */ new Map();
    endpoint.on("message", (data) => {
      if (!data?.id) {
        return;
      }
      const resolver = pendingListeners.get(data.id);
      if (!resolver) {
        return;
      }
      try {
        resolver(data);
      } finally {
        pendingListeners.delete(data.id);
      }
    });
    return createProxy({ endpoint, pendingListeners, rootMarkerID });
  }
  function throwIfProxyReleased(isReleased) {
    if (isReleased) {
      throw new Error("Proxy has been released and is not useable");
    }
  }
  async function releaseEndpoint(epWithPendingListeners) {
    await requestResponseMessage(epWithPendingListeners, { type: MessageType.RELEASE });
    epWithPendingListeners.endpoint.close?.();
  }
  var proxyCounter = /* @__PURE__ */ new WeakMap();
  var proxyFinalizers = "FinalizationRegistry" in globalThis && new FinalizationRegistry((epWithPendingListeners) => {
    const newCount = (proxyCounter.get(epWithPendingListeners) ?? 0) - 1;
    proxyCounter.set(epWithPendingListeners, newCount);
    if (newCount === 0) {
      releaseEndpoint(epWithPendingListeners).finally(() => {
        epWithPendingListeners.pendingListeners.clear();
      });
    }
  });
  function registerProxy(proxy2, epWithPendingListeners) {
    const newCount = (proxyCounter.get(epWithPendingListeners) ?? 0) + 1;
    proxyCounter.set(epWithPendingListeners, newCount);
    if (proxyFinalizers) {
      proxyFinalizers.register(proxy2, epWithPendingListeners, proxy2);
    }
  }
  function unregisterProxy(proxy2) {
    if (proxyFinalizers) {
      proxyFinalizers.unregister(proxy2);
    }
  }
  function createProxy(epWithPendingListeners, path = []) {
    let isProxyReleased = false;
    const propProxyCache = /* @__PURE__ */ new Map();
    const proxy2 = new Proxy(function() {
    }, {
      get(_target, prop) {
        throwIfProxyReleased(isProxyReleased);
        if (prop === releaseProxy) {
          return async () => {
            for (const subProxy of propProxyCache.values()) {
              subProxy[releaseProxy]();
            }
            propProxyCache.clear();
            unregisterProxy(proxy2);
            releaseEndpoint(epWithPendingListeners).finally(() => {
              epWithPendingListeners.pendingListeners.clear();
            });
            isProxyReleased = true;
          };
        }
        if (prop === "then") {
          if (path.length === 0) {
            return { then: () => proxy2 };
          }
          const r = requestResponseMessage(epWithPendingListeners, {
            type: MessageType.GET,
            path: path.map((p) => p.toString())
          }).then((v) => fromWireValue(v, epWithPendingListeners.endpoint));
          return r.then.bind(r);
        }
        const cachedProxy = propProxyCache.get(prop);
        if (cachedProxy) {
          return cachedProxy;
        }
        const propProxy = createProxy(epWithPendingListeners, [...path, prop]);
        propProxyCache.set(prop, propProxy);
        return propProxy;
      },
      set(_target, prop, rawValue) {
        throwIfProxyReleased(isProxyReleased);
        const [value, transfer] = toWireValue(rawValue, epWithPendingListeners.endpoint);
        return requestResponseMessage(epWithPendingListeners, {
          type: MessageType.SET,
          path: [...path, prop].map((p) => p.toString()),
          value
        }, transfer).then((v) => fromWireValue(v, epWithPendingListeners.endpoint));
      },
      apply(_target, _thisArg, rawArgumentList) {
        throwIfProxyReleased(isProxyReleased);
        const last = path[path.length - 1];
        if (last === "bind") {
          return createProxy(epWithPendingListeners, path.slice(0, -1));
        }
        const [argumentList, transfer] = processArguments(rawArgumentList, epWithPendingListeners);
        return requestResponseMessage(epWithPendingListeners, {
          type: MessageType.APPLY,
          path: path.map((p) => p.toString()),
          argumentList
        }, transfer).then((v) => fromWireValue(v, epWithPendingListeners.endpoint));
      },
      construct(_target, rawArgumentList) {
        throwIfProxyReleased(isProxyReleased);
        const [argumentList, transfer] = processArguments(rawArgumentList, epWithPendingListeners);
        return requestResponseMessage(epWithPendingListeners, {
          type: MessageType.CONSTRUCT,
          path: path.map((p) => p.toString()),
          argumentList
        }, transfer).then((v) => fromWireValue(v, epWithPendingListeners.endpoint));
      }
    });
    registerProxy(proxy2, epWithPendingListeners);
    return proxy2;
  }
  var transferCache = /* @__PURE__ */ new WeakMap();
  function processArguments(argumentList, epWithPendingListeners) {
    const wireValues = [];
    const transferables = [];
    for (const argument of argumentList) {
      const [wireValue, transfer] = toWireValue(argument, epWithPendingListeners.endpoint);
      wireValues.push(wireValue);
      transferables.push(...transfer);
    }
    return [wireValues, transferables];
  }
  function proxy(obj) {
    return Object.assign(obj, { [proxyMarker]: randomId() });
  }
  function toWireValue(value, ep) {
    for (const [name, handler] of transferHandlers) {
      if (handler.canHandle(value)) {
        const [serializedValue, transfer] = handler.serialize(value, ep);
        return [{
          type: WireValueType.HANDLER,
          name,
          value: serializedValue
        }, transfer];
      }
    }
    return [{
      type: WireValueType.RAW,
      value
    }, transferCache.get(value) ?? []];
  }
  function fromWireValue(value, ep) {
    switch (value.type) {
      case WireValueType.HANDLER:
        return transferHandlers.get(value.name).deserialize(value.value, ep);
      case WireValueType.RAW:
        return value.value;
    }
  }
  function requestResponseMessage(ep, msg, transfer) {
    return new Promise((resolve) => {
      const id = randomId();
      ep.pendingListeners.set(id, resolve);
      ep.endpoint.postMessage({ id, ...msg, markerID: ep.rootMarkerID }, transfer);
    });
  }
  var hex = [];
  var alphabet = "0123456789abcdef";
  for (let i = 0; i < 256; i++) {
    hex[i] = alphabet[i >> 4 & 15] + alphabet[i & 15];
  }
  var step = 0;
  var buffer = "";
  function randomId() {
    let i = 0;
    if (!buffer || step + 16 > 256 * 2) {
      for (buffer = "", step = 0; i < 256; ++i) {
        buffer += hex[Math.random() * 256 | 0];
      }
    }
    return buffer.substring(step, ++step + 16);
  }

  // node_modules/abslink/adapters/w3c.js
  function createWrapper(channel, messageable) {
    const listeners = /* @__PURE__ */ new WeakMap();
    channel.start?.();
    messageable.start?.();
    return {
      on(event, listener) {
        const unwrapped = (event2) => listener(event2.data);
        if ("addEventListener" in channel) {
          channel.addEventListener(event, unwrapped);
        } else if ("addListener" in channel) {
          channel.addListener(event, unwrapped);
        } else {
          channel.on(event, unwrapped);
        }
        listeners.set(listener, unwrapped);
      },
      off(event, listener) {
        const unwrapped = listeners.get(listener);
        if ("removeEventListener" in channel) {
          channel.removeEventListener(event, unwrapped);
        } else if ("removeListener" in channel) {
          channel.removeListener(event, unwrapped);
        } else {
          channel.off(event, unwrapped);
        }
        listeners.delete(listener);
      },
      postMessage(message, transfer) {
        messageable.postMessage(message, transfer);
      },
      close() {
        if (channel !== globalThis)
          channel.close?.();
        if (messageable !== globalThis)
          messageable.close?.();
      }
    };
  }
  function wrap2(channel, messageable = channel) {
    return wrap(createWrapper(channel, messageable));
  }

  // node_modules/jassub/src/debug.ts
  var import_throughput = __toESM(require_throughput(), 1);
  var Debug = class {
    constructor() {
      // 5 second average
      __publicField(this, "fps", (0, import_throughput.default)(5));
      __publicField(this, "processingDuration", (0, import_throughput.default)(5));
      __publicField(this, "droppedFrames", 0);
      __publicField(this, "presentedFrames", 0);
      __publicField(this, "mistimedFrames", 0);
      __publicField(this, "_startTime", 0);
      __publicField(this, "onsubtitleFrameCallback", console.log);
    }
    _drop() {
      ++this.droppedFrames;
    }
    _startFrame() {
      this._startTime = performance.now();
    }
    _endFrame(meta) {
      ++this.presentedFrames;
      const fps = this.fps(1);
      const now = performance.now();
      const processingDuration = this.processingDuration((now - this._startTime) / fps);
      const frameDelay = Math.max(0, meta.expectedDisplayTime - now);
      if (frameDelay) ++this.mistimedFrames;
      this.onsubtitleFrameCallback?.(now, {
        fps,
        processingDuration,
        droppedFrames: this.droppedFrames,
        presentedFrames: this.presentedFrames,
        mistimedFrames: this.mistimedFrames,
        presentationTime: now,
        expectedDisplayTime: meta.expectedDisplayTime + (frameDelay > 0 ? fps / 1e3 : 0),
        frameDelay,
        width: meta.width,
        height: meta.height,
        mediaTime: meta.mediaTime
      });
      console.info(
        "%cFPS: %c%f %c| Frame Time: %c%d ms %c| Dropped Frames: %c%d %c| 5s Avg",
        "color: #888",
        "color: #0f0; font-weight: bold",
        fps.toFixed(1),
        "color: #888",
        "color: #0ff; font-weight: bold",
        processingDuration,
        "color: #888",
        "color: #f00; font-weight: bold",
        this.droppedFrames,
        "color: #888"
      );
    }
  };

  // node_modules/jassub/src/jassub.ts
  var import_meta = {};
  var webYCbCrMap = {
    rgb: "RGB",
    bt709: "BT709",
    // these might not be exactly correct? oops?
    bt470bg: "BT601",
    // alias BT.601 PAL... whats the difference?
    smpte170m: "BT601"
    // alias BT.601 NTSC... whats the difference?
  };
  var _JASSUB = class _JASSUB {
    constructor(opts) {
      __publicField(this, "timeOffset");
      __publicField(this, "prescaleFactor");
      __publicField(this, "prescaleHeightLimit");
      __publicField(this, "maxRenderHeight");
      __publicField(this, "debug");
      __publicField(this, "renderer");
      __publicField(this, "ready");
      __publicField(this, "busy", false);
      __publicField(this, "_video");
      __publicField(this, "_videoWidth", 0);
      __publicField(this, "_videoHeight", 0);
      __publicField(this, "_videoColorSpace", null);
      __publicField(this, "_canvas");
      __publicField(this, "_canvasParent");
      __publicField(this, "_ctrl", new AbortController());
      __publicField(this, "_ro", new ResizeObserver(() => this.resize()));
      __publicField(this, "_destroyed", false);
      __publicField(this, "_lastDemandTime");
      __publicField(this, "_skipped", false);
      __publicField(this, "_worker");
      if (!globalThis.Worker) throw new Error("Worker not supported");
      if (!opts) throw new Error("No options provided");
      if (!opts.video && !opts.canvas) throw new Error("You should give video or canvas in options.");
      _JASSUB._test();
      this.timeOffset = opts.timeOffset ?? 0;
      this._video = opts.video;
      this._canvas = opts.canvas ?? document.createElement("canvas");
      if (this._video && !opts.canvas) {
        this._canvasParent = document.createElement("div");
        this._canvasParent.className = "JASSUB";
        this._canvasParent.style.position = "relative";
        this._canvas.style.display = "block";
        this._canvas.style.position = "absolute";
        this._canvas.style.pointerEvents = "none";
        this._canvasParent.appendChild(this._canvas);
        this._video.insertAdjacentElement("afterend", this._canvasParent);
      }
      const ctrl = this._canvas.transferControlToOffscreen();
      this.debug = opts.debug ? new Debug() : null;
      this.prescaleFactor = opts.prescaleFactor ?? 1;
      this.prescaleHeightLimit = opts.prescaleHeightLimit ?? 1080;
      this.maxRenderHeight = opts.maxRenderHeight ?? 0;
      this._worker = opts.workerUrl ? new Worker(opts.workerUrl, { name: "jassub-worker", type: "module" }) : new Worker(new URL("./worker/worker.js", import_meta.url), { name: "jassub-worker", type: "module" });
      const Renderer = wrap2(this._worker);
      const modern = opts.modernWasmUrl ?? new URL("./wasm/jassub-worker-modern.wasm", import_meta.url).href;
      const fallback = opts.wasmUrl ?? new URL("./wasm/jassub-worker.wasm", import_meta.url).href;
      this.ready = (async () => {
        this.renderer = await new Renderer({
          wasmUrl: _JASSUB._supportsSIMD ? modern : fallback,
          width: ctrl.width,
          height: ctrl.height,
          subUrl: opts.subUrl,
          subContent: opts.subContent ?? null,
          fonts: opts.fonts ?? [],
          availableFonts: opts.availableFonts ?? { "liberation sans": "./default.woff2" },
          fallbackFont: opts.fallbackFont ?? "liberation sans",
          debug: !!opts.debug,
          libassMemoryLimit: opts.libassMemoryLimit ?? 0,
          libassGlyphLimit: opts.libassGlyphLimit ?? 0,
          // @ts-expect-error TS doesn't know about queryLocalFonts
          useLocalFonts: typeof queryLocalFonts !== "undefined" && (opts.useLocalFonts ?? true)
        }, proxy((font) => this._getLocalFont(font)));
        await this.renderer.ready();
      })();
      if (this._video) this.setVideo(this._video);
      this._worker.postMessage({ name: "offscreenCanvas", ctrl }, [ctrl]);
    }
    static _test() {
      if (_JASSUB._supportsSIMD != null) return;
      try {
        _JASSUB._supportsSIMD = WebAssembly.validate(Uint8Array.of(0, 97, 115, 109, 1, 0, 0, 0, 1, 5, 1, 96, 0, 1, 123, 3, 2, 1, 0, 10, 10, 1, 8, 0, 65, 0, 253, 15, 253, 98, 11));
      } catch (e) {
        _JASSUB._supportsSIMD = false;
      }
      const module = new WebAssembly.Module(Uint8Array.of(0, 97, 115, 109, 1, 0, 0, 0));
      if (!(module instanceof WebAssembly.Module) || !(new WebAssembly.Instance(module) instanceof WebAssembly.Instance)) throw new Error("WASM not supported");
    }
    async resize(force = !!this._video?.paused, width = 0, height = 0, top = 0, left = 0) {
      await this.ready;
      if ((!width || !height) && this._video) {
        const videoSize = this._getVideoPosition();
        let renderSize = null;
        if (this._videoWidth) {
          const widthRatio = this._video.videoWidth / this._videoWidth;
          const heightRatio = this._video.videoHeight / this._videoHeight;
          renderSize = this._computeCanvasSize((videoSize.width || 0) / widthRatio, (videoSize.height || 0) / heightRatio);
        } else {
          renderSize = this._computeCanvasSize(videoSize.width || 0, videoSize.height || 0);
        }
        width = renderSize.width;
        height = renderSize.height;
        if (this._canvasParent) {
          top = videoSize.y - (this._canvasParent.getBoundingClientRect().top - this._video.getBoundingClientRect().top);
          left = videoSize.x;
        }
        this._canvas.style.width = videoSize.width + "px";
        this._canvas.style.height = videoSize.height + "px";
      }
      this._canvas.style.top = top + "px";
      this._canvas.style.left = left + "px";
      await this.renderer._canvas(
        width,
        height,
        (this._videoWidth || this._video?.videoWidth) ?? width,
        (this._videoHeight || this._video?.videoHeight) ?? height
      );
      if (force && this._lastDemandTime) this._demandRender();
    }
    _getVideoPosition(width = this._video.videoWidth, height = this._video.videoHeight) {
      const videoRatio = width / height;
      const { offsetWidth, offsetHeight } = this._video;
      const elementRatio = offsetWidth / offsetHeight;
      width = offsetWidth;
      height = offsetHeight;
      if (elementRatio > videoRatio) {
        width = Math.floor(offsetHeight * videoRatio);
      } else {
        height = Math.floor(offsetWidth / videoRatio);
      }
      const x = (offsetWidth - width) / 2;
      const y = (offsetHeight - height) / 2;
      return { width, height, x, y };
    }
    _computeCanvasSize(width = 0, height = 0) {
      const scalefactor = this.prescaleFactor <= 0 ? 1 : this.prescaleFactor;
      const ratio = self.devicePixelRatio || 1;
      if (height <= 0 || width <= 0) {
        width = 0;
        height = 0;
      } else {
        const sgn = scalefactor < 1 ? -1 : 1;
        let newH = height * ratio;
        if (sgn * newH * scalefactor <= sgn * this.prescaleHeightLimit) {
          newH *= scalefactor;
        } else if (sgn * newH < sgn * this.prescaleHeightLimit) {
          newH = this.prescaleHeightLimit;
        }
        if (this.maxRenderHeight > 0 && newH > this.maxRenderHeight) newH = this.maxRenderHeight;
        width *= newH / height;
        height = newH;
      }
      return { width, height };
    }
    async setVideo(video) {
      await this.ready;
      if (video instanceof HTMLVideoElement) {
        this._removeListeners();
        this._video = video;
        this._video.requestVideoFrameCallback((now, data) => this._handleRVFC(data));
        if ("VideoFrame" in globalThis) {
          video.addEventListener("loadedmetadata", () => this._updateColorSpace(), this._ctrl);
          if (video.readyState > 2) this._updateColorSpace();
        }
        if (video.videoWidth > 0) this.resize();
        this._ro.observe(video);
      } else {
        throw new Error("Video element invalid!");
      }
    }
    async _sendLocalFont(name) {
      try {
        const fontData = await queryLocalFonts();
        const font = fontData?.find((obj) => obj.fullName.toLowerCase() === name);
        if (font) {
          const blob = await font.blob();
          this.renderer.addFont(new Uint8Array(await blob.arrayBuffer()));
        }
      } catch (e) {
        console.warn("Local fonts API:", e);
      }
    }
    async _getLocalFont(font) {
      try {
        if (navigator?.permissions?.query) {
          const permission = await navigator.permissions.query({ name: "local-fonts" });
          if (permission.state === "granted") {
            await this._sendLocalFont(font);
          }
        } else {
          await this._sendLocalFont(font);
        }
      } catch (e) {
        console.warn("Local fonts API:", e);
      }
    }
    _handleRVFC(data) {
      if (this._destroyed) return;
      this._lastDemandTime = data;
      this._demandRender();
      this._video.requestVideoFrameCallback((now, data2) => this._handleRVFC(data2));
    }
    async _demandRender() {
      const { mediaTime, width, height } = this._lastDemandTime;
      if (width !== this._videoWidth || height !== this._videoHeight) {
        this._videoWidth = width;
        this._videoHeight = height;
        this.resize(false);
      }
      if (this.busy) {
        this._skipped = true;
        this.debug?._drop();
        return;
      }
      this.busy = true;
      this._skipped = false;
      this.debug?._startFrame();
      await this.renderer._draw(mediaTime + this.timeOffset);
      this.debug?._endFrame(this._lastDemandTime);
      this.busy = false;
      if (this._skipped) this._demandRender();
    }
    async _updateColorSpace() {
      await this.ready;
      this._video.requestVideoFrameCallback(async () => {
        try {
          const frame = new VideoFrame(this._video);
          frame.close();
          await this.renderer._setColorSpace(webYCbCrMap[frame.colorSpace.matrix]);
        } catch (e) {
          console.warn(e);
        }
      });
    }
    _removeListeners() {
      if (this._video) {
        if (this._ro) this._ro.unobserve(this._video);
        this._ctrl.abort();
        this._ctrl = new AbortController();
      }
    }
    async destroy() {
      if (this._destroyed) return;
      this._destroyed = true;
      if (this._video && this._canvasParent) this._video.parentNode?.removeChild(this._canvasParent);
      this._removeListeners();
      await this.renderer[releaseProxy]();
      this._worker.terminate();
    }
  };
  __publicField(_JASSUB, "_supportsSIMD");
  var JASSUB = _JASSUB;
  return __toCommonJS(jassub_exports);
})();
