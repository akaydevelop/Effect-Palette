/**
 * host.jsx — ExtendScript
 */

if (!String.prototype.trim) {
  String.prototype.trim = function() {
    return this.replace(/^\s+|\s+$/g, "");
  };
}

function normalize(str) {
  return String(str).toLowerCase().replace(/\s+/g, " ").trim();
}

function diagnose() {
  try {
    app.enableQE();
    if (typeof qe === "undefined") return "qe não existe";
    if (!qe.project) return "qe.project não existe — abra um projeto";
    var list = qe.project.getVideoEffectList();
    var sel  = app.project.activeSequence ? app.project.activeSequence.getSelection() : [];
    return "OK — effects: " + list.length + " | selected clips: " + (sel ? sel.length : 0);
  } catch(e) {
    return "Erro: " + e.message;
  }
}

// ─── 1. Exportar lista de efeitos ─────────────────────────────────────────────

function getProjectIdentity() {
  try {
    if (!app.project || !app.project.rootItem) return "";

    var projectName = "";
    var projectPath = "";
    try { projectName = String(app.project.name || ""); } catch (e0) {}
    try { projectPath = String(app.project.path || ""); } catch (e1) {}

    return JSON.stringify({
      name: projectName,
      path: projectPath
    });
  } catch (e) {
    return "";
  }
}

function getEffectsList() {
  try {
    app.enableQE();
    if (typeof qe === "undefined" || !qe.project) {
      return "Error: QE DOM não disponível. Abra um projeto no Premiere primeiro.";
    }

    var effects = [];
    var seen    = {};

    var videoList = qe.project.getVideoEffectList();
    for (var i = 0; i < videoList.length; i++) {
      var name = String(videoList[i]).trim();
      if (!name || seen[name]) continue;
      seen[name] = true;
      effects.push({ name: name, category: "Video", type: "video" });
    }

    var audioList = qe.project.getAudioEffectList();
    for (var j = 0; j < audioList.length; j++) {
      var aname = String(audioList[j]).trim();
      if (!aname || seen[aname]) continue;
      seen[aname] = true;
      effects.push({ name: aname, category: "Audio", type: "audio" });
    }

    effects.sort(function(a, b) { return a.name.localeCompare(b.name); });
    return JSON.stringify(effects);

  } catch (e) {
    return "Error: " + e.message;
  }
}

// ─── 2. Capturar seleção atual ────────────────────────────────────────────────

function getSelectionJSON() {
  try {
    var sequence = app.project.activeSequence;
    if (!sequence) return "[]";

    var selection = sequence.getSelection();
    if (!selection || selection.length === 0) return "[]";

    var result = [];
    var seen   = {};

    for (var s = 0; s < selection.length; s++) {
      var clip = selection[s];

      var trackIndex = clip.parentTrackIndex;
      var isAudio    = false;

      var numVideoTracks = sequence.videoTracks.numTracks;
      if (trackIndex >= numVideoTracks) {
        isAudio    = true;
        trackIndex = trackIndex - numVideoTracks;
      }

      if (trackIndex < 0) continue;

      var key = trackIndex + "_" + clip.start.ticks + "_" + clip.name + "_" + isAudio;
      if (seen[key]) continue;
      seen[key] = true;

      var timingInfo = _buildKeyframeTimingInfo(clip, {
        clipName: clip.name,
        endTicks: clip.end && clip.end.ticks !== undefined ? clip.end.ticks : "",
        inPointTicks: clip.inPoint && clip.inPoint.ticks !== undefined ? clip.inPoint.ticks : "",
        outPointTicks: clip.outPoint && clip.outPoint.ticks !== undefined ? clip.outPoint.ticks : ""
      });

      result.push({
        startTicks: clip.start.ticks,
        endTicks: clip.end && clip.end.ticks !== undefined ? clip.end.ticks : "",
        inPointTicks: clip.inPoint && clip.inPoint.ticks !== undefined ? clip.inPoint.ticks : "",
        outPointTicks: clip.outPoint && clip.outPoint.ticks !== undefined ? clip.outPoint.ticks : "",
        clipName:   clip.name,
        trackIndex: trackIndex,
        isAudio:    isAudio,
        isImageLike: !!(timingInfo && timingInfo.isImageLike),
        isAdjustmentLike: !!(timingInfo && timingInfo.isAdjustmentLike),
        looksLikeInfiniteStill: !!(timingInfo && timingInfo.looksLikeInfiniteStill)
      });
    }

    return JSON.stringify(result);
  } catch(e) {
    return "[]";
  }
}

// ─── 3. Verificar se efeito existe ────────────────────────────────────────────

function _projectTreeCategory(treePath) {
  var raw = String(treePath || "");
  if (!raw) return "Projeto";

  var parts = raw.split("\\");
  var clean = [];
  for (var i = 0; i < parts.length; i++) {
    if (parts[i]) clean.push(parts[i]);
  }

  if (clean.length <= 2) return "Projeto";

  var categoryParts = [];
  for (i = 1; i < clean.length - 1; i++) {
    categoryParts.push(clean[i]);
  }

  return categoryParts.length ? categoryParts.join(" > ") : "Projeto";
}

function _collectProjectItemsRecursive(projectItem, out) {
  if (!projectItem || !out) return;

  var itemType = "";
  var isSequence = false;
  var mediaPath = "";
  var treePath = "";
  var itemName = "";

  try { itemType = String(projectItem.type || ""); } catch (e0) {}
  try { isSequence = !!(typeof projectItem.isSequence === "function" && projectItem.isSequence()); } catch (e1) {}
  try { treePath = String(projectItem.treePath || ""); } catch (e2) {}
  try {
    if (typeof projectItem.getMediaPath === "function") {
      mediaPath = String(projectItem.getMediaPath() || "");
    }
  } catch (e3) {}
  try { itemName = String(projectItem.name || ""); } catch (e4) {}

  var isInsertable = !!(
    isSequence ||
    mediaPath ||
    itemType === "1" ||
    itemType === "CLIP" ||
    itemType === "FILE"
  );

  var isTemplateAsset = false;
  if (
    /(^|\\)template_project\.prproj(\\|$)/i.test(treePath) &&
    (
      /^(Adjustment Layer_\d+x\d+|AL_TEMPLATE_\d+x\d+)$/i.test(itemName) ||
      /(^|\\)Adjustment Layers \[[^\\]+\](\\|$)/i.test(treePath)
    )
  ) {
    isTemplateAsset = true;
  }

  if (isInsertable && !isTemplateAsset) {
    out.push({
      name: String(projectItem.name || ""),
      category: _projectTreeCategory(treePath),
      type: "project_item",
      nodeId: String(projectItem.nodeId || ""),
      itemType: itemType,
      isSequence: isSequence,
      treePath: treePath,
      mediaPath: mediaPath
    });
  }

  try {
    if (projectItem.children && projectItem.children.numItems) {
      for (var i = 0; i < projectItem.children.numItems; i++) {
        _collectProjectItemsRecursive(projectItem.children[i], out);
      }
    }
  } catch (childrenErr) {}
}

function getProjectItemsList() {
  try {
    if (!app.project || !app.project.rootItem) {
      return "Error: Projeto não disponível.";
    }

    var items = [];
    _collectProjectItemsRecursive(app.project.rootItem, items);

    items.sort(function(a, b) {
      var an = String(a.name || "").toLowerCase();
      var bn = String(b.name || "").toLowerCase();
      if (an < bn) return -1;
      if (an > bn) return 1;
      return 0;
    });

    return JSON.stringify(items);
  } catch (e) {
    return "Error: " + e.message;
  }
}

function getProjectItemsListSafe() {
  try {
    if (!app.project || !app.project.rootItem) return "[]";

    var items = [];
    _collectProjectItemsRecursive(app.project.rootItem, items);

    items.sort(function(a, b) {
      var an = String(a.name || "").toLowerCase();
      var bn = String(b.name || "").toLowerCase();
      if (an < bn) return -1;
      if (an > bn) return 1;
      return 0;
    });

    return JSON.stringify(items);
  } catch (e) {
    return "Error: " + e.message;
  }
}

function getSequencesListSafe() {
  try {
    if (!app.project || !app.project.sequences) return "[]";

    var sequences = [];
    var total = 0;
    try { total = app.project.sequences.numSequences || 0; } catch (e0) {}

    for (var i = 0; i < total; i++) {
      var sequence = app.project.sequences[i];
      if (!sequence) continue;

      var name = "";
      var sequenceID = "";
      var width = 0;
      var height = 0;
      var timebase = "";
      var projectItemNodeId = "";

      try { name = String(sequence.name || ""); } catch (e1) {}
      try { sequenceID = String(sequence.sequenceID || ""); } catch (e2) {}
      try { width = Number(sequence.frameSizeVertical) || 0; } catch (e3) {}
      try { height = Number(sequence.frameSizeHorizontal) || 0; } catch (e4) {}
      try { timebase = String(sequence.timebase || ""); } catch (e5) {}
      try {
        if (sequence.projectItem) {
          projectItemNodeId = String(sequence.projectItem.nodeId || "");
        }
      } catch (e6) {}

      sequences.push({
        name: name,
        sequenceID: sequenceID,
        width: width,
        height: height,
        label: (width > 0 && height > 0) ? (width + "x" + height) : "",
        timebase: timebase,
        projectItemNodeId: projectItemNodeId
      });
    }

    return JSON.stringify(sequences);
  } catch (e) {
    return "Error: " + e.message;
  }
}

function _findBinByName(projectItem, targetName) {
  if (!projectItem || !targetName) return null;

  var itemName = "";
  var itemType = "";
  try { itemName = String(projectItem.name || ""); } catch (e0) {}
  try { itemType = String(projectItem.type || ""); } catch (e1) {}
  if (itemName === targetName && (itemType === "2" || itemType === "BIN")) {
    return projectItem;
  }

  try {
    if (projectItem.children && projectItem.children.numItems) {
      for (var i = 0; i < projectItem.children.numItems; i++) {
        var found = _findBinByName(projectItem.children[i], targetName);
        if (found) return found;
      }
    }
  } catch (e2) {}

  return null;
}

function _favoriteCategoryLabel(parts) {
  if (!parts || !parts.length) return "Favoritos";
  return "Favoritos > " + parts.join(" > ");
}

function _collectFavoriteItemsRecursive(projectItem, pathParts, out, sourceProjectPath) {
  if (!projectItem || !out) return;

  var itemName = "";
  var itemType = "";
  var isSequence = false;
  var mediaPath = "";
  var sequenceID = "";
  try { itemName = String(projectItem.name || ""); } catch (e0) {}
  try { itemType = String(projectItem.type || ""); } catch (e1) {}
  try { isSequence = !!(typeof projectItem.isSequence === "function" && projectItem.isSequence()); } catch (e2) {}
  try {
    if (typeof projectItem.getMediaPath === "function") {
      mediaPath = String(projectItem.getMediaPath() || "");
    }
  } catch (e3) {}

  if (isSequence) {
    var total = 0;
    try { total = app.project.sequences ? (app.project.sequences.numSequences || 0) : 0; } catch (e4) {}
    for (var si = 0; si < total; si++) {
      var sequence = null;
      try { sequence = app.project.sequences[si]; } catch (e5) {}
      if (!sequence || !sequence.projectItem) continue;
      if (sequence.projectItem !== projectItem) continue;
      try { sequenceID = String(sequence.sequenceID || ""); } catch (e6) {}
      break;
    }
  }

  var favoriteType = "";
  if (isSequence && sequenceID) {
    favoriteType = "sequence";
  } else if (mediaPath) {
    favoriteType = "media";
  }

  if (favoriteType) {
    out.push({
      name: itemName,
      category: _favoriteCategoryLabel(pathParts),
      favoriteType: favoriteType,
      sourceProjectPath: sourceProjectPath || "",
      sourceTreePath: String(projectItem.treePath || ""),
      mediaPath: mediaPath,
      sequenceID: sequenceID,
      isSequence: isSequence,
      itemType: itemType
    });
  }

  try {
    if (projectItem.children && projectItem.children.numItems) {
      for (var i = 0; i < projectItem.children.numItems; i++) {
        var child = projectItem.children[i];
        if (!child) continue;

        var childType = "";
        var childName = "";
        try { childType = String(child.type || ""); } catch (e7) {}
        try { childName = String(child.name || ""); } catch (e8) {}

        if (childType === "2" || childType === "BIN") {
          var nextParts = pathParts ? pathParts.slice(0) : [];
          if (childName) nextParts.push(childName);
          _collectFavoriteItemsRecursive(child, nextParts, out, sourceProjectPath);
        } else {
          _collectFavoriteItemsRecursive(child, pathParts, out, sourceProjectPath);
        }
      }
    }
  } catch (e9) {}
}

function getTemplateFavoritesListSafe() {
  try {
    if (!app.project || !app.project.rootItem) {
      return JSON.stringify({ rootFound: false, items: [] });
    }

    var currentProjectPath = "";
    try { currentProjectPath = String(app.project.path || ""); } catch (ePre0) {}
    var expectedTemplatePath = _resolveTemplateProjectPath("");
    var normalizedCurrentProjectPath = String(currentProjectPath || "").replace(/\\/g, "/").toLowerCase();
    var normalizedExpectedTemplatePath = String(expectedTemplatePath || "").replace(/\\/g, "/").toLowerCase();
    if (!normalizedCurrentProjectPath || !normalizedExpectedTemplatePath || normalizedCurrentProjectPath !== normalizedExpectedTemplatePath) {
      return JSON.stringify({ rootFound: false, items: [] });
    }

    var rootBin = _findBinByName(app.project.rootItem, "EffectPalette_Favorites");
    if (!rootBin) {
      return JSON.stringify({ rootFound: false, items: [] });
    }

    var items = [];
    var sourceProjectPath = currentProjectPath;

    try {
      if (rootBin.children && rootBin.children.numItems) {
        for (var i = 0; i < rootBin.children.numItems; i++) {
          var child = rootBin.children[i];
          if (!child) continue;

          var childType = "";
          var childName = "";
          try { childType = String(child.type || ""); } catch (e1) {}
          try { childName = String(child.name || ""); } catch (e2) {}

          if (childType === "2" || childType === "BIN") {
            _collectFavoriteItemsRecursive(child, childName ? [childName] : [], items, sourceProjectPath);
          } else {
            _collectFavoriteItemsRecursive(child, [], items, sourceProjectPath);
          }
        }
      }
    } catch (e3) {}

    items.sort(function(a, b) {
      var ac = String(a.category || "").toLowerCase();
      var bc = String(b.category || "").toLowerCase();
      if (ac < bc) return -1;
      if (ac > bc) return 1;
      var an = String(a.name || "").toLowerCase();
      var bn = String(b.name || "").toLowerCase();
      if (an < bn) return -1;
      if (an > bn) return 1;
      return 0;
    });

    return JSON.stringify({
      rootFound: true,
      sourceProjectPath: sourceProjectPath,
      items: items
    });
  } catch (e) {
    return "Error: " + e.message;
  }
}

function _findProjectItemByNodeId(projectItem, nodeId) {
  if (!projectItem || !nodeId) return null;

  try {
    if (String(projectItem.nodeId || "") === String(nodeId)) {
      return projectItem;
    }
  } catch (e0) {}

  try {
    if (projectItem.children && projectItem.children.numItems) {
      for (var i = 0; i < projectItem.children.numItems; i++) {
        var found = _findProjectItemByNodeId(projectItem.children[i], nodeId);
        if (found) return found;
      }
    }
  } catch (e1) {}

  return null;
}

function _resolveInsertionTracks(sequence, selectionJSON) {
  var videoTracks = sequence && sequence.videoTracks ? sequence.videoTracks.numTracks : 0;
  var audioTracks = sequence && sequence.audioTracks ? sequence.audioTracks.numTracks : 0;
  var targetVideo = 0;
  var targetAudio = 0;
  var selection = [];
  var i;
  var item;

  try {
    selection = selectionJSON ? JSON.parse(selectionJSON) : [];
  } catch (e0) {
    selection = [];
  }

  for (i = 0; i < selection.length; i++) {
    item = selection[i];
    if (!item) continue;
    if (item.isAudio) {
      if (audioTracks > 0 && item.trackIndex >= 0 && item.trackIndex < audioTracks) {
        targetAudio = item.trackIndex;
        break;
      }
    }
  }

  for (i = 0; i < selection.length; i++) {
    item = selection[i];
    if (!item || item.isAudio) continue;
    if (videoTracks > 0 && item.trackIndex >= 0 && item.trackIndex < videoTracks) {
        targetVideo = item.trackIndex;
        break;
    }
  }

  if (videoTracks < 1) targetVideo = 0;
  if (audioTracks < 1) targetAudio = 0;

  return {
    videoTrackIndex: targetVideo,
    audioTrackIndex: targetAudio
  };
}

function _trackHasClipAtTicks(track, ticks) {
  if (!track || !track.clips) return false;

  var playheadTicks = Number(ticks) || 0;
  try {
    for (var i = 0; i < track.clips.numItems; i++) {
      var clip = track.clips[i];
      if (!clip || !clip.start || !clip.end) continue;

      var startTicks = Number(clip.start.ticks) || 0;
      var endTicks = Number(clip.end.ticks) || 0;
      if (playheadTicks >= startTicks && playheadTicks < endTicks) {
        return true;
      }
    }
  } catch (e) {}

  return false;
}

function _trackHasClipInRange(track, startTicks, endTicks) {
  if (!track || !track.clips) return false;

  var rangeStart = Number(startTicks) || 0;
  var rangeEnd = Number(endTicks) || rangeStart;
  try {
    for (var i = 0; i < track.clips.numItems; i++) {
      var clip = track.clips[i];
      if (!clip || !clip.start || !clip.end) continue;

      var clipStart = Number(clip.start.ticks) || 0;
      var clipEnd = Number(clip.end.ticks) || 0;
      if (rangeStart < clipEnd && rangeEnd > clipStart) {
        return true;
      }
    }
  } catch (e) {}

  return false;
}

function _ensureVideoTrackIndex(sequence, targetIndex) {
  if (!sequence || targetIndex < 0) return false;

  try {
    var safety = 0;
    while (sequence.videoTracks.numTracks <= targetIndex && safety < 8) {
      app.enableQE();
      if (typeof qe === "undefined" || !qe.project) return false;

      var qeSequence = qe.project.getActiveSequence();
      if (!qeSequence || typeof qeSequence.addTracks !== "function") return false;

      var currentTracks = sequence.videoTracks.numTracks;
      var insertAfter = currentTracks;
      qeSequence.addTracks(1, insertAfter, 0);
      safety++;
    }
  } catch (e) {
    return false;
  }

  return sequence.videoTracks.numTracks > targetIndex;
}

function _findAvailableVideoTrackAtTicks(sequence, startIndex, ticks) {
  if (!sequence || !sequence.videoTracks) return startIndex;

  var targetIndex = startIndex;
  while (targetIndex < sequence.videoTracks.numTracks) {
    var track = sequence.videoTracks[targetIndex];
    if (!_trackHasClipAtTicks(track, ticks)) {
      return targetIndex;
    }
    targetIndex++;
  }

  if (_ensureVideoTrackIndex(sequence, targetIndex)) {
    var rescanIndex = startIndex;
    while (rescanIndex < sequence.videoTracks.numTracks) {
      if (!_trackHasClipAtTicks(sequence.videoTracks[rescanIndex], ticks)) {
        return rescanIndex;
      }
      rescanIndex++;
    }
  }

  return startIndex;
}

function _findAvailableVideoTrackInRange(sequence, startIndex, startTicks, endTicks) {
  if (!sequence || !sequence.videoTracks) return startIndex;

  var targetIndex = startIndex;
  while (targetIndex < sequence.videoTracks.numTracks) {
    var track = sequence.videoTracks[targetIndex];
    if (!_trackHasClipInRange(track, startTicks, endTicks)) {
      return targetIndex;
    }
    targetIndex++;
  }

  if (_ensureVideoTrackIndex(sequence, targetIndex)) {
    var rescanIndex = startIndex;
    while (rescanIndex < sequence.videoTracks.numTracks) {
      if (!_trackHasClipInRange(sequence.videoTracks[rescanIndex], startTicks, endTicks)) {
        return rescanIndex;
      }
      rescanIndex++;
    }
  }

  return startIndex;
}

function _trackHasAudioClipAtTicks(track, ticks) {
  return _trackHasClipAtTicks(track, ticks);
}

function _ensureAudioTrackIndex(sequence, targetIndex) {
  if (!sequence || targetIndex < 0) return false;

  try {
    var safety = 0;
    while (sequence.audioTracks.numTracks <= targetIndex && safety < 8) {
      app.enableQE();
      if (typeof qe === "undefined" || !qe.project) return false;

      var qeSequence = qe.project.getActiveSequence();
      if (!qeSequence || typeof qeSequence.addTracks !== "function") return false;

      var currentTracks = sequence.audioTracks.numTracks;
      var insertAfter = currentTracks;

      // addTracks(addVideoNum, addToVideoIndex, addAudioNum, audioType, addToAudioIndex)
      qeSequence.addTracks(0, 0, 1, 3, insertAfter);
      safety++;
    }
  } catch (e) {
    return false;
  }

  return sequence.audioTracks.numTracks > targetIndex;
}

function _findAvailableAudioTrackAtTicks(sequence, startIndex, ticks) {
  if (!sequence || !sequence.audioTracks) return startIndex;

  var targetIndex = startIndex;
  while (targetIndex < sequence.audioTracks.numTracks) {
    var track = sequence.audioTracks[targetIndex];
    if (!_trackHasAudioClipAtTicks(track, ticks)) {
      return targetIndex;
    }
    targetIndex++;
  }

  if (_ensureAudioTrackIndex(sequence, targetIndex)) {
    var rescanIndex = startIndex;
    while (rescanIndex < sequence.audioTracks.numTracks) {
      if (!_trackHasAudioClipAtTicks(sequence.audioTracks[rescanIndex], ticks)) {
        return rescanIndex;
      }
      rescanIndex++;
    }
  }

  return startIndex;
}

function _describeTrackOccupancy(trackCollection, ticks) {
  var parts = [];
  if (!trackCollection) return "";

  try {
    for (var i = 0; i < trackCollection.numTracks; i++) {
      var track = trackCollection[i];
      var trackName = "";
      try { trackName = String(track.name || ""); } catch (e0) {}
      parts.push(i + ":" + trackName + ":" + (_trackHasClipAtTicks(track, ticks) ? "busy" : "free"));
    }
  } catch (e1) {}

  return parts.join(" | ");
}

function _projectItemMediaKinds(projectItem) {
  var mediaPath = "";
  var isSequence = false;
  var itemName = "";
  var lowerPath = "";
  var audioExts = {
    ".wav": true, ".mp3": true, ".aif": true, ".aiff": true, ".m4a": true,
    ".aac": true, ".ogg": true, ".flac": true, ".wma": true
  };
  var imageExts = {
    ".png": true, ".jpg": true, ".jpeg": true, ".bmp": true, ".gif": true,
    ".tif": true, ".tiff": true, ".webp": true, ".psd": true
  };

  try { isSequence = !!(typeof projectItem.isSequence === "function" && projectItem.isSequence()); } catch (e0) {}
  try { itemName = String(projectItem.name || ""); } catch (e0b) {}
  try {
    if (typeof projectItem.getMediaPath === "function") {
      mediaPath = String(projectItem.getMediaPath() || "");
    }
  } catch (e1) {}

  lowerPath = String(mediaPath || "").toLowerCase();
  var dot = lowerPath.lastIndexOf(".");
  var ext = dot >= 0 ? lowerPath.substring(dot) : "";

  if (isSequence) {
    return { hasVideo: true, hasAudio: true };
  }
  if (audioExts[ext]) {
    return { hasVideo: false, hasAudio: true };
  }
  if (imageExts[ext]) {
    return { hasVideo: true, hasAudio: false };
  }
  if (!mediaPath && /adjustment layer/i.test(itemName)) {
    return { hasVideo: true, hasAudio: false };
  }
  if (!mediaPath && !isSequence) {
    return { hasVideo: true, hasAudio: false };
  }

  return { hasVideo: true, hasAudio: true };
}

function _isAdjustmentLayerItem(projectItem) {
  var itemName = "";
  try { itemName = String(projectItem.name || ""); } catch (e) {}
  return /adjustment layer/i.test(itemName);
}

function _selectionVideoSpan(selectionJSON) {
  var selection = [];
  var minStart = null;
  var maxEnd = null;
  var count = 0;

  try {
    selection = selectionJSON ? JSON.parse(selectionJSON) : [];
  } catch (e0) {
    selection = [];
  }

  for (var i = 0; i < selection.length; i++) {
    var item = selection[i];
    if (!item || item.isAudio) continue;

    var startTicks = Number(item.startTicks);
    var endTicks = Number(item.endTicks);
    if (isNaN(startTicks) || isNaN(endTicks) || endTicks <= startTicks) continue;

    if (minStart === null || startTicks < minStart) minStart = startTicks;
    if (maxEnd === null || endTicks > maxEnd) maxEnd = endTicks;
    count++;
  }

  if (minStart === null || maxEnd === null || count < 2) return null;
  return {
    startTicks: minStart,
    endTicks: maxEnd,
    count: count
  };
}

function _timeFromTicks(ticks) {
  var t = new Time();
  var numericTicks = Math.max(0, Math.round(Number(ticks) || 0));
  t.ticks = String(numericTicks);
  try {
    t.seconds = numericTicks / 254016000000;
  } catch (e) {}
  return t;
}

function _findClipByStartOnTrack(track, startTicks, clipName) {
  if (!track || !track.clips) return null;
  var targetTicks = Number(startTicks) || 0;

  try {
    for (var i = 0; i < track.clips.numItems; i++) {
      var clip = track.clips[i];
      if (!clip || !clip.start) continue;
      var clipStart = Number(clip.start.ticks) || 0;
      if (Math.abs(clipStart - targetTicks) > 200000) continue;
      if (clipName && String(clip.name || "") !== String(clipName)) continue;
      return clip;
    }
  } catch (e) {}

  return null;
}

function _extensionRootFsPath() {
  try {
    return File($.fileName).parent.parent.fsName;
  } catch (e) {
    return "";
  }
}

function _readJSONFile(fsPath) {
  if (!fsPath) return null;
  var file = new File(fsPath);
  if (!file.exists) return null;

  try {
    file.encoding = "UTF-8";
    if (!file.open("r")) return null;
    var text = file.read();
    file.close();
    return text ? JSON.parse(text) : null;
  } catch (e) {
    try { file.close(); } catch (closeErr) {}
    return null;
  }
}

function _getSequenceCreateSettings(sequence) {
  var settings = {
    width: 1920,
    height: 1080,
    timeBase: 254016000000 / 30,
    parNum: 1,
    parDen: 1,
    audioSampleRate: 48000
  };

  try {
    if (sequence && typeof sequence.getSettings === "function") {
      var seqSettings = sequence.getSettings();
      if (seqSettings) {
        if (seqSettings.videoFrameWidth) settings.width = Number(seqSettings.videoFrameWidth) || settings.width;
        if (seqSettings.videoFrameHeight) settings.height = Number(seqSettings.videoFrameHeight) || settings.height;
        if (seqSettings.videoPixelAspectRatioNumerator) settings.parNum = Number(seqSettings.videoPixelAspectRatioNumerator) || settings.parNum;
        if (seqSettings.videoPixelAspectRatioDenominator) settings.parDen = Number(seqSettings.videoPixelAspectRatioDenominator) || settings.parDen;
        if (seqSettings.audioSampleRate) settings.audioSampleRate = Number(seqSettings.audioSampleRate) || settings.audioSampleRate;
      }
    }
  } catch (e0) {}

  try {
    if (sequence && sequence.timebase) settings.timeBase = Number(sequence.timebase) || settings.timeBase;
  } catch (e1) {}

  return settings;
}

function _collectProjectItemsMatching(projectItem, matcher, out) {
  if (!projectItem || !matcher || !out) return;

  try {
    if (matcher(projectItem)) out.push(projectItem);
  } catch (e0) {}

  try {
    if (projectItem.children && projectItem.children.numItems) {
      for (var i = 0; i < projectItem.children.numItems; i++) {
        _collectProjectItemsMatching(projectItem.children[i], matcher, out);
      }
    }
  } catch (e1) {}
}

function _findFirstProjectItemMatching(matcher) {
  if (!app.project || !app.project.rootItem || !matcher) return null;
  var matches = [];
  _collectProjectItemsMatching(app.project.rootItem, matcher, matches);
  return matches.length ? matches[0] : null;
}

function _ensureEffectPaletteAssetsBin() {
  if (!app.project || !app.project.rootItem) return null;

  var existing = _findFirstProjectItemMatching(function(item) {
    var name = "";
    var itemType = "";
    try { name = String(item.name || ""); } catch (e0) {}
    try { itemType = String(item.type || ""); } catch (e1) {}
    return name === "EffectPalette_Assets" && (itemType === "2" || itemType === "BIN");
  });
  if (existing) return existing;

  try {
    return app.project.rootItem.createBin("EffectPalette_Assets");
  } catch (e2) {
    return null;
  }
}

function _moveProjectItemToBin(projectItem, targetBin) {
  if (!projectItem || !targetBin || projectItem === targetBin) return;
  try {
    if (typeof projectItem.moveBin === "function") {
      projectItem.moveBin(targetBin);
    }
  } catch (e) {}
}

function _organizeGenericAsset(projectItem) {
  if (!projectItem) return projectItem;
  var assetsBin = _ensureEffectPaletteAssetsBin();
  _moveProjectItemToBin(projectItem, assetsBin);
  return projectItem;
}

function _deleteSequenceIfPossible(sequence) {
  if (!sequence || !app.project || typeof app.project.deleteSequence !== "function") return false;
  try {
    return !!app.project.deleteSequence(sequence);
  } catch (e) {
    return false;
  }
}

function _deleteImportedTemplateSequences(templateName, preserveSequence) {
  if (!templateName || !app.project || !app.project.sequences) return 0;

  var deleted = 0;
  var activeSequence = null;
  try { activeSequence = app.project.activeSequence || null; } catch (e0) {}

  var total = 0;
  try { total = app.project.sequences.numSequences || 0; } catch (e1) {}

  for (var i = total - 1; i >= 0; i--) {
    var sequence = null;
    try { sequence = app.project.sequences[i]; } catch (e2) {}
    if (!sequence) continue;
    if (preserveSequence && sequence === preserveSequence) continue;
    if (activeSequence && sequence === activeSequence) continue;

    var seqName = "";
    try { seqName = String(sequence.name || ""); } catch (e3) {}
    if (seqName !== templateName) continue;

    if (_deleteSequenceIfPossible(sequence)) deleted++;
  }

  return deleted;
}

function _findFirstNewInsertableProjectItem(beforeRootCount) {
  if (!app.project || !app.project.rootItem) return null;
  var root = app.project.rootItem;
  var startIndex = Number(beforeRootCount);
  if (isNaN(startIndex) || startIndex < 0) startIndex = 0;

  for (var i = startIndex; i < root.children.numItems; i++) {
    var candidate = root.children[i];
    if (!candidate) continue;

    var directKinds = _projectItemMediaKinds(candidate);
    if (directKinds.hasVideo || directKinds.hasAudio) return candidate;

    var nested = [];
    _collectProjectItemsMatching(candidate, function(item) {
      var kinds = _projectItemMediaKinds(item);
      return kinds.hasVideo || kinds.hasAudio;
    }, nested);
    if (nested.length) return nested[0];
  }

  return null;
}

function _matchesProjectItemName(projectItem, pattern) {
  if (!projectItem || !pattern) return false;
  var name = "";
  try { name = String(projectItem.name || ""); } catch (e) {}
  return pattern.test(name);
}

function _findAdjustmentLayerProjectItem() {
  return _findFirstProjectItemMatching(function(item) {
    return _matchesProjectItemName(item, /adjustment layer/i);
  });
}

function _expectedAdjustmentLayerName(width, height) {
  var w = Number(width) || 0;
  var h = Number(height) || 0;
  if (!w || !h) return "";
  return "Adjustment Layer_" + w + "x" + h;
}

function _findAdjustmentLayerProjectItemBySize(width, height) {
  var expectedName = _expectedAdjustmentLayerName(width, height);
  if (!expectedName) return null;

  return _findFirstProjectItemMatching(function(item) {
    var name = "";
    try { name = String(item.name || ""); } catch (e) {}
    return name === expectedName;
  });
}

function _findGenericProjectItem(genericKey) {
  var patterns = {
    adjustment_layer: /adjustment layer/i,
    bars_and_tone: /bars and tone/i,
    black_video: /black video/i,
    color_matte: /color matte/i,
    transparent_video: /transparent video/i,
    universal_counting_leader: /universal counting leader/i
  };
  var pattern = patterns[genericKey];
  if (!pattern) return null;

  return _findFirstProjectItemMatching(function(item) {
    return _matchesProjectItemName(item, pattern);
  });
}

function _findProjectItemByMediaPath(mediaPath) {
  if (!mediaPath) return null;

  return _findFirstProjectItemMatching(function(item) {
    var candidatePath = "";
    try {
      if (typeof item.getMediaPath === "function") {
        candidatePath = String(item.getMediaPath() || "");
      }
    } catch (e) {}
    return candidatePath && String(candidatePath) === String(mediaPath);
  });
}

function _findSequenceProjectItemByName(sequenceName) {
  if (!sequenceName || !app.project || !app.project.sequences) return null;

  var total = 0;
  try { total = app.project.sequences.numSequences || 0; } catch (e0) {}
  for (var i = 0; i < total; i++) {
    var sequence = null;
    try { sequence = app.project.sequences[i]; } catch (e1) {}
    if (!sequence || !sequence.projectItem) continue;

    var currentName = "";
    try { currentName = String(sequence.name || ""); } catch (e2) {}
    if (currentName === String(sequenceName)) return sequence.projectItem;
  }

  return null;
}

function _resolveTemplateProjectPath(rawProjectPath) {
  var rootPath = _extensionRootFsPath();
  if (!rootPath) return "";

  var resolved = String(rawProjectPath || "");
  if (!resolved) {
    resolved = "template_project/template_project.prproj";
  }

  if (resolved.indexOf(":") < 0 && resolved.indexOf("/") !== 0 && resolved.indexOf("\\") !== 0) {
    resolved = rootPath + "/" + resolved;
  }

  return resolved;
}

function _importFavoriteProjectItem(itemName, mediaPath, sequenceID, favoriteType, sourceProjectPath) {
  var assetsBin = _ensureEffectPaletteAssetsBin() || (app.project ? app.project.rootItem : null);

  if (favoriteType === "sequence" || sequenceID) {
    var existingSequenceItem = _findSequenceProjectItemByName(itemName);
    if (existingSequenceItem) return _organizeGenericAsset(existingSequenceItem);

    var projectPath = _resolveTemplateProjectPath(sourceProjectPath);
    if (!projectPath) return "template_missing";

    var beforeRootCount = app.project.rootItem.children.numItems;
    var importResult = app.project.importSequences(projectPath, [String(sequenceID || "")]);
    if (importResult !== 0 && importResult !== true) return "create_failed";

    try {
      for (var i = beforeRootCount; i < app.project.rootItem.children.numItems; i++) {
        var candidate = app.project.rootItem.children[i];
        if (!candidate) continue;
        _moveProjectItemToBin(candidate, assetsBin);
      }
    } catch (e0) {}

    var importedSequenceItem = _findSequenceProjectItemByName(itemName);
    return importedSequenceItem ? _organizeGenericAsset(importedSequenceItem) : "not_found";
  }

  if (favoriteType === "media" || mediaPath) {
    var existingMediaItem = _findProjectItemByMediaPath(mediaPath);
    if (existingMediaItem) return _organizeGenericAsset(existingMediaItem);

    try {
      var importFileResult = app.project.importFiles([String(mediaPath || "")], true, assetsBin, false);
      if (importFileResult !== 0 && importFileResult !== true) return "create_failed";
    } catch (e1) {
      return "create_failed";
    }

    var importedMediaItem = _findProjectItemByMediaPath(mediaPath);
    return importedMediaItem ? _organizeGenericAsset(importedMediaItem) : "not_found";
  }

  return "not_supported";
}

function _importAdjustmentLayerFromTemplate() {
  var rootPath = _extensionRootFsPath();
  if (!rootPath) return "template_missing";

  var config = _readJSONFile(rootPath + "/data/generic_item_templates.json");
  if (!config || !config.adjustmentLayer) return "template_missing";

  var template = config.adjustmentLayer;
  var rawProjectPath = String(template.projectPath || "");
  if (!rawProjectPath) return "template_missing";

  var projectPath = rawProjectPath;
  if (rawProjectPath.indexOf(":") < 0 && rawProjectPath.indexOf("/") !== 0 && rawProjectPath.indexOf("\\") !== 0) {
    projectPath = rootPath + "/" + rawProjectPath;
  }

  var chosenWidth = 0;
  var chosenHeight = 0;
  var chosenTemplateName = "";
  var sequenceIDs = [];
  var settings = _getSequenceCreateSettings(app.project.activeSequence);
  var targetWidth = Number(settings.width) || 0;
  var targetHeight = Number(settings.height) || 0;

  if (template.templates && template.templates.length) {
    var bestIndex = -1;
    var bestScore = -1;
    for (var ti = 0; ti < template.templates.length; ti++) {
      var entry = template.templates[ti];
      if (!entry) continue;
      var entrySequenceID = String(entry.sequenceID || "");
      if (!entrySequenceID) continue;

      var entryWidth = Number(entry.width) || 0;
      var entryHeight = Number(entry.height) || 0;
      var score = Math.abs(entryWidth - targetWidth) + Math.abs(entryHeight - targetHeight);

      if (bestIndex < 0 || score < bestScore) {
        bestIndex = ti;
        bestScore = score;
      }
    }

    if (bestIndex >= 0) {
      chosenWidth = Number(template.templates[bestIndex].width) || 0;
      chosenHeight = Number(template.templates[bestIndex].height) || 0;
      chosenTemplateName = String(template.templates[bestIndex].name || "");
      sequenceIDs = [String(template.templates[bestIndex].sequenceID || "")];
    }
  } else {
    sequenceIDs = template.sequenceIDs || [];
  }

  if (!sequenceIDs.length || !sequenceIDs[0]) return "template_missing";

  if (chosenWidth && chosenHeight) {
    var existingSizedLayer = _findAdjustmentLayerProjectItemBySize(chosenWidth, chosenHeight);
    if (existingSizedLayer) return existingSizedLayer;
  }

  var beforeRootCount = app.project.rootItem.children.numItems;
  var beforeSequenceCount = 0;
  var importedSequences = [];
  try {
    beforeSequenceCount = app.project.sequences ? (app.project.sequences.numSequences || 0) : 0;
  } catch (seqCountErr) {}
  var importResult = app.project.importSequences(projectPath, sequenceIDs);
  if (importResult !== 0 && importResult !== true) return "create_failed";

  var assetsBin = _ensureEffectPaletteAssetsBin();

  try {
    var totalSequences = app.project.sequences ? (app.project.sequences.numSequences || 0) : 0;
    for (var si = beforeSequenceCount; si < totalSequences; si++) {
      var importedSequence = app.project.sequences[si];
      if (!importedSequence) continue;

      if (!chosenTemplateName || String(importedSequence.name || "") === chosenTemplateName) {
        importedSequences.push(importedSequence);
      }
    }
  } catch (moveSeqErr) {}

  var resolvedItem = null;
  for (var i = beforeRootCount; i < app.project.rootItem.children.numItems; i++) {
    var candidate = app.project.rootItem.children[i];
    if (!candidate) continue;

    _moveProjectItemToBin(candidate, assetsBin);

    var matches = [];
    _collectProjectItemsMatching(candidate, function(item) {
      if (chosenWidth && chosenHeight) {
        var expectedName = _expectedAdjustmentLayerName(chosenWidth, chosenHeight);
        var itemName = "";
        try { itemName = String(item.name || ""); } catch (e) {}
        return itemName === expectedName;
      }
      return _matchesProjectItemName(item, /adjustment layer/i);
    }, matches);
    if (matches.length) {
      resolvedItem = matches[0];
      break;
    }
  }

  if (!resolvedItem) {
    resolvedItem =
      (chosenWidth && chosenHeight ? _findAdjustmentLayerProjectItemBySize(chosenWidth, chosenHeight) : null) ||
      null;
  }

  for (var ds = importedSequences.length - 1; ds >= 0; ds--) {
    _deleteSequenceIfPossible(importedSequences[ds]);
  }
  if (chosenTemplateName) {
    _deleteImportedTemplateSequences(chosenTemplateName, null);
  }

  return resolvedItem || "not_found";
}

function _createGenericProjectItem(genericKey, sequence) {
  var settings = _getSequenceCreateSettings(sequence);
  var beforeRootCount = app.project.rootItem.children.numItems;

  if (genericKey === "adjustment_layer") {
    return (
      _findAdjustmentLayerProjectItemBySize(settings.width, settings.height) ||
      _importAdjustmentLayerFromTemplate() ||
      _findAdjustmentLayerProjectItem() ||
      "not_found"
    );
  }

  var existingGeneric = _findGenericProjectItem(genericKey);
  if (existingGeneric) return existingGeneric;

  if (genericKey === "bars_and_tone") {
    try {
      return _organizeGenericAsset(app.project.newBarsAndTone(
        settings.width,
        settings.height,
        settings.timeBase,
        settings.parNum,
        settings.parDen,
        settings.audioSampleRate,
        "Bars and Tone"
      )) || "create_failed";
    } catch (barsErr) {
      return "create_failed";
    }
  }

  try {
    app.enableQE();
    if (typeof qe === "undefined" || !qe.project) return "create_failed";

    if (genericKey === "black_video") {
      if (!qe.project.newBlackVideo(settings.width, settings.height, settings.timeBase, settings.parNum, settings.parDen)) return "create_failed";
    } else if (genericKey === "color_matte") {
      if (!qe.project.newColorMatte(settings.width, settings.height, settings.timeBase, settings.parNum, settings.parDen)) return "create_failed";
    } else if (genericKey === "transparent_video") {
      if (!qe.project.newTransparentVideo(settings.width, settings.height, settings.timeBase, settings.parNum, settings.parDen)) return "create_failed";
    } else if (genericKey === "universal_counting_leader") {
      if (!qe.project.newUniversalCountingLeader(settings.width, settings.height, settings.timeBase, settings.parNum, settings.parDen, settings.audioSampleRate)) return "create_failed";
    } else {
      return "create_failed";
    }
  } catch (qeErr) {
    return "create_failed";
  }

  return _organizeGenericAsset(_findFirstNewInsertableProjectItem(beforeRootCount)) || "not_found";
}

function _projectItemShouldSpanSelection(projectItem, explicitGenericKey) {
  var key = String(explicitGenericKey || "");
  if (key === "adjustment_layer" || key === "bars_and_tone" || key === "black_video" || key === "color_matte" || key === "transparent_video" || key === "universal_counting_leader") {
    return true;
  }

  var name = "";
  try { name = String(projectItem.name || ""); } catch (e) {}
  return /adjustment layer|bars and tone|black video|color matte|transparent video|universal counting leader/i.test(name);
}

function _insertResolvedProjectItem(sequence, projectItem, selectionJSON, explicitGenericKey) {
  if (!sequence || !projectItem) return "not_found";

  var playhead = sequence.getPlayerPosition();
  if (!playhead) return "Error: NÃ£o foi possÃ­vel obter o playhead.";

  var tracks = _resolveInsertionTracks(sequence, selectionJSON);
  var playheadTicks = playhead.ticks !== undefined ? playhead.ticks : playhead;
  var insertionTicks = Number(playheadTicks) || 0;
  var mediaKinds = _projectItemMediaKinds(projectItem);
  var selectionSpan = _projectItemShouldSpanSelection(projectItem, explicitGenericKey) ? _selectionVideoSpan(selectionJSON) : null;
  var result = null;
  var timeSeconds = String(playhead.seconds);
  var timeTicks = String(playheadTicks);

  if (selectionSpan) {
    insertionTicks = selectionSpan.startTicks;
    timeTicks = String(insertionTicks);
    timeSeconds = String(insertionTicks / 254016000000);
  }

  if (mediaKinds.hasVideo) {
    tracks.videoTrackIndex = selectionSpan
      ? _findAvailableVideoTrackInRange(sequence, tracks.videoTrackIndex, selectionSpan.startTicks, selectionSpan.endTicks)
      : _findAvailableVideoTrackAtTicks(sequence, tracks.videoTrackIndex, insertionTicks);
  }
  if (mediaKinds.hasAudio) {
    tracks.audioTrackIndex = _findAvailableAudioTrackAtTicks(sequence, tracks.audioTrackIndex, insertionTicks);
  }

  try {
    if (mediaKinds.hasVideo && !mediaKinds.hasAudio && sequence.videoTracks[tracks.videoTrackIndex]) {
      result = sequence.videoTracks[tracks.videoTrackIndex].overwriteClip(projectItem, timeTicks);
    } else if (!mediaKinds.hasVideo && mediaKinds.hasAudio && sequence.audioTracks[tracks.audioTrackIndex]) {
      result = sequence.audioTracks[tracks.audioTrackIndex].overwriteClip(projectItem, timeTicks);
    } else {
      result = sequence.overwriteClip(projectItem, timeSeconds, tracks.videoTrackIndex, tracks.audioTrackIndex);
    }
  } catch (e1) {
    try {
      result = sequence.insertClip(projectItem, playhead, tracks.videoTrackIndex, tracks.audioTrackIndex);
    } catch (e2) {
      try {
        result = sequence.insertClip(projectItem, String(playhead.ticks), tracks.videoTrackIndex, tracks.audioTrackIndex);
      } catch (e3) {
        return "Error: " + e3.message;
      }
    }
  }

  if (selectionSpan && mediaKinds.hasVideo && sequence.videoTracks[tracks.videoTrackIndex]) {
    var insertedClip = _findClipByStartOnTrack(
      sequence.videoTracks[tracks.videoTrackIndex],
      selectionSpan.startTicks,
      projectItem.name
    );
    if (insertedClip) {
      try {
        insertedClip.end = _timeFromTicks(selectionSpan.endTicks);
      } catch (trimErr) {}
    }
  }

  if (result === false) return "Error: overwriteClip retornou false.";
  return "ok";
}

function insertProjectItemAtPlayhead(nodeId, selectionJSON) {
  try {
    var sequence = app.project.activeSequence;
    if (!sequence) return "no_sequence";
    if (!app.project || !app.project.rootItem) return "not_found";

    var projectItem = _findProjectItemByNodeId(app.project.rootItem, nodeId);
    if (!projectItem) return "not_found";

    var playhead = sequence.getPlayerPosition();
    if (!playhead) return "Error: Não foi possível obter o playhead.";

    var tracks = _resolveInsertionTracks(sequence, selectionJSON);
    var playheadTicks = playhead.ticks !== undefined ? playhead.ticks : playhead;
    var insertionTicks = Number(playheadTicks) || 0;
    var mediaKinds = _projectItemMediaKinds(projectItem);
    var selectionSpan = _isAdjustmentLayerItem(projectItem) ? _selectionVideoSpan(selectionJSON) : null;
    var result = null;
    var timeSeconds = String(playhead.seconds);
    var timeTicks = String(playheadTicks);
    var initialVideoTrackIndex = tracks.videoTrackIndex;
    var initialAudioTrackIndex = tracks.audioTrackIndex;

    if (selectionSpan) {
      insertionTicks = selectionSpan.startTicks;
      timeTicks = String(insertionTicks);
      timeSeconds = String(insertionTicks / 254016000000);
    }

    if (mediaKinds.hasVideo) {
      tracks.videoTrackIndex = selectionSpan
        ? _findAvailableVideoTrackInRange(sequence, tracks.videoTrackIndex, selectionSpan.startTicks, selectionSpan.endTicks)
        : _findAvailableVideoTrackAtTicks(sequence, tracks.videoTrackIndex, insertionTicks);
    }
    if (mediaKinds.hasAudio) {
      tracks.audioTrackIndex = _findAvailableAudioTrackAtTicks(sequence, tracks.audioTrackIndex, insertionTicks);
    }

    try {
      if (mediaKinds.hasVideo && !mediaKinds.hasAudio && sequence.videoTracks[tracks.videoTrackIndex]) {
        result = sequence.videoTracks[tracks.videoTrackIndex].overwriteClip(projectItem, timeTicks);
      } else if (!mediaKinds.hasVideo && mediaKinds.hasAudio && sequence.audioTracks[tracks.audioTrackIndex]) {
        result = sequence.audioTracks[tracks.audioTrackIndex].overwriteClip(projectItem, timeTicks);
      } else {
        result = sequence.overwriteClip(projectItem, timeSeconds, tracks.videoTrackIndex, tracks.audioTrackIndex);
      }
    } catch (e1) {
      try {
        result = sequence.insertClip(projectItem, playhead, tracks.videoTrackIndex, tracks.audioTrackIndex);
      } catch (e2) {
        try {
          result = sequence.insertClip(projectItem, String(playhead.ticks), tracks.videoTrackIndex, tracks.audioTrackIndex);
        } catch (e3) {
          return "Error: " + e3.message;
        }
      }
    }

    if (selectionSpan && mediaKinds.hasVideo && sequence.videoTracks[tracks.videoTrackIndex]) {
      var insertedClip = _findClipByStartOnTrack(
        sequence.videoTracks[tracks.videoTrackIndex],
        selectionSpan.startTicks,
        projectItem.name
      );
      if (insertedClip) {
        try {
          insertedClip.end = _timeFromTicks(selectionSpan.endTicks);
        } catch (trimErr) {}
      }
    }

    if (result === false) return "Error: overwriteClip retornou false.";
    return JSON.stringify({
      status: "ok",
      debug: {
        initialVideoTrackIndex: initialVideoTrackIndex,
        resolvedVideoTrackIndex: tracks.videoTrackIndex,
        initialAudioTrackIndex: initialAudioTrackIndex,
        resolvedAudioTrackIndex: tracks.audioTrackIndex,
        playheadTicks: timeTicks,
        selectionSpan: selectionSpan,
        mediaKinds: mediaKinds,
        videoTracks: _describeTrackOccupancy(sequence.videoTracks, insertionTicks),
        audioTracks: _describeTrackOccupancy(sequence.audioTracks, insertionTicks)
      }
    });
  } catch (e) {
    return "Error: " + e.message;
  }
}

function insertProjectItemAtPlayhead(nodeId, selectionJSON) {
  try {
    var sequence = app.project.activeSequence;
    if (!sequence) return "no_sequence";
    if (!app.project || !app.project.rootItem) return "not_found";

    var projectItem = _findProjectItemByNodeId(app.project.rootItem, nodeId);
    if (!projectItem) return "not_found";

    return _insertResolvedProjectItem(sequence, projectItem, selectionJSON, "");
  } catch (e) {
    return "Error: " + e.message;
  }
}

function insertGenericItemAtPlayhead(genericKey, selectionJSON) {
  try {
    var sequence = app.project.activeSequence;
    if (!sequence) return "no_sequence";
    if (!app.project || !app.project.rootItem) return "not_found";

    var projectItem = _createGenericProjectItem(genericKey, sequence);
    if (projectItem === "template_missing") return "template_missing";
    if (projectItem === "create_failed") return "create_failed";
    if (projectItem === "not_found" || !projectItem) return "not_found";

    return _insertResolvedProjectItem(sequence, projectItem, selectionJSON, genericKey);
  } catch (e) {
    return "Error: " + e.message;
  }
}

function insertFavoriteItemAtPlayhead(itemName, mediaPath, sequenceID, favoriteType, sourceProjectPath, selectionJSON) {
  try {
    var sequence = app.project.activeSequence;
    if (!sequence) return "no_sequence";
    if (!app.project || !app.project.rootItem) return "not_found";

    var projectItem = _importFavoriteProjectItem(itemName, mediaPath, sequenceID, favoriteType, sourceProjectPath);
    if (projectItem === "template_missing") return "template_missing";
    if (projectItem === "create_failed") return "create_failed";
    if (projectItem === "not_supported") return "not_supported";
    if (projectItem === "not_found" || !projectItem) return "not_found";

    return _insertResolvedProjectItem(sequence, projectItem, selectionJSON, "");
  } catch (e) {
    return "Error: " + e.message;
  }
}

function effectExists(effectName, effectType) {
  try {
    app.enableQE();
    var list = (effectType === "audio")
      ? qe.project.getAudioEffectList()
      : qe.project.getVideoEffectList();

    var normalTarget = normalize(effectName);
    for (var i = 0; i < list.length; i++) {
      if (normalize(String(list[i]).trim()) === normalTarget) return "true";
    }
    return "false";
  } catch(e) {
    return "false";
  }
}

// ─── 4. Aplicar efeito com seleção passada como parâmetro ────────────────────

function applyEffectWithSelection(effectName, effectType, selectionJSON) {
  try {
    app.enableQE();
    if (typeof qe === "undefined" || !qe.project) {
      return "Error: QE DOM não disponível.";
    }

    var selection = JSON.parse(selectionJSON);
    if (!selection || selection.length === 0) return "no_selection";

    var list = (effectType === "audio")
      ? qe.project.getAudioEffectList()
      : qe.project.getVideoEffectList();

    var resolvedName = null;
    var normalTarget = normalize(effectName);
    for (var k = 0; k < list.length; k++) {
      var candidate = String(list[k]).trim();
      if (normalize(candidate) === normalTarget) {
        resolvedName = candidate;
        break;
      }
    }

    if (!resolvedName) return "not_found";

    var effectObj = (effectType === "audio")
      ? qe.project.getAudioEffectByName(resolvedName)
      : qe.project.getVideoEffectByName(resolvedName);

    if (!effectObj) return "not_found";

    var qeSequence = qe.project.getActiveSequence();
    if (!qeSequence) return "Error: Nenhuma sequência ativa.";

    var applied = 0;

    for (var s = 0; s < selection.length; s++) {
      var saved    = selection[s];
      var useAudio = saved.isAudio || (effectType === "audio");

      var qeTrack = useAudio
        ? qeSequence.getAudioTrackAt(saved.trackIndex)
        : qeSequence.getVideoTrackAt(saved.trackIndex);

      if (!qeTrack) continue;

      for (var qc = 0; qc < qeTrack.numItems; qc++) {
        var qeClip = qeTrack.getItemAt(qc);
        if (!qeClip) continue;

        if (Math.abs(qeClip.start.ticks - saved.startTicks) < 200000) {
          if (useAudio) {
            qeClip.addAudioEffect(effectObj);
          } else {
            qeClip.addVideoEffect(effectObj);
          }
          applied++;
          break;
        }
      }
    }

    return applied > 0 ? "ok" : "no_selection";

  } catch (e) {
    return "Error: " + e.message;
  }
}

// ─── 5. Aplicar preset com seleção passada como parâmetro ────────────────────

function _normName(str) {
  return String(str).toLowerCase().replace(/[\u2018\u2019']/g, "'").trim();
}

function _ticksClose(a, b) {
  return Math.abs(Number(a) - Number(b)) < 200000;
}

function _findQeClipOnTrack(qeTrack, startTicks) {
  if (!qeTrack) return null;
  for (var i = 0; i < qeTrack.numItems; i++) {
    var qeClip = qeTrack.getItemAt(i);
    if (qeClip && _ticksClose(qeClip.start.ticks, startTicks)) {
      return qeClip;
    }
  }
  return null;
}

function _findStdClipOnTrack(stdTrack, startTicks, clipName) {
  if (!stdTrack) return null;

  var fallback = null;
  for (var i = 0; i < stdTrack.clips.numItems; i++) {
    var stdClip = stdTrack.clips[i];
    if (!stdClip || !_ticksClose(stdClip.start.ticks, startTicks)) continue;

    if (clipName && stdClip.name === clipName) {
      return stdClip;
    }
    if (!fallback) fallback = stdClip;
  }

  return fallback;
}

function _resolveClipContext(sequence, qeSequence, saved, wantAudio) {
  var qeTrack = null;
  var stdTrack = null;
  var qeClip = null;
  var stdClip = null;
  var i;

  if (wantAudio === saved.isAudio) {
    qeTrack = wantAudio
      ? qeSequence.getAudioTrackAt(saved.trackIndex)
      : qeSequence.getVideoTrackAt(saved.trackIndex);
    stdTrack = wantAudio
      ? sequence.audioTracks[saved.trackIndex]
      : sequence.videoTracks[saved.trackIndex];

      qeClip = _findQeClipOnTrack(qeTrack, saved.startTicks);
      stdClip = _findStdClipOnTrack(stdTrack, saved.startTicks, saved.clipName);
      if (qeClip && stdClip) {
        return { qeClip: qeClip, stdClip: stdClip, trackIndex: saved.trackIndex, saved: saved };
      }
  }

  if (wantAudio) {
    for (i = 0; i < sequence.audioTracks.numTracks; i++) {
      qeTrack = qeSequence.getAudioTrackAt(i);
      stdTrack = sequence.audioTracks[i];
        qeClip = _findQeClipOnTrack(qeTrack, saved.startTicks);
        stdClip = _findStdClipOnTrack(stdTrack, saved.startTicks, saved.clipName);
        if (qeClip && stdClip) {
          return { qeClip: qeClip, stdClip: stdClip, trackIndex: i, saved: saved };
        }
      }
  } else {
    for (i = 0; i < sequence.videoTracks.numTracks; i++) {
      qeTrack = qeSequence.getVideoTrackAt(i);
      stdTrack = sequence.videoTracks[i];
        qeClip = _findQeClipOnTrack(qeTrack, saved.startTicks);
        stdClip = _findStdClipOnTrack(stdTrack, saved.startTicks, saved.clipName);
        if (qeClip && stdClip) {
          return { qeClip: qeClip, stdClip: stdClip, trackIndex: i, saved: saved };
        }
      }
  }

  return null;
}

function _canonicalEffectName(str) {
  return _normName(str || "")
    .replace(/\((legacy|obsolete|obsoleto|legado)\)/g, "")
    .replace(/\blegacy\b/g, "")
    .replace(/\bobsolete\b/g, "")
    .replace(/[()]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function _legacyEffectAlias(displayName, matchName) {
  var normalizedMatch = _normName(matchName || "");
  var aliasByMatch = {
    "ae.adbe motion blur": "Directional Blur (Legacy)",
    "ae.adbe gaussian blur 2": "Gaussian Blur (Legacy)",
    "ae.adbe mosaic": "Mosaic (Legacy)"
  };

  if (aliasByMatch[normalizedMatch]) return aliasByMatch[normalizedMatch];
  return null;
}

function _resolveEffectObject(displayName, matchName, isAudioFx, effectMeta) {
  var effectObj = null;
  var lookupNames = [];
  var seenLookupNames = {};
  var legacyAlias = effectMeta && effectMeta.legacyAlias
    ? effectMeta.legacyAlias
    : (!isAudioFx ? _legacyEffectAlias(displayName, matchName) : null);
  function addLookupName(name) {
    var key;
    if (!name) return;
    key = _normName(name);
    if (seenLookupNames[key]) return;
    seenLookupNames[key] = true;
    lookupNames.push(name);
  }

  if (effectMeta && effectMeta.resolvedEffectName) addLookupName(effectMeta.resolvedEffectName);
  if (effectMeta && effectMeta.lookupCandidates && effectMeta.lookupCandidates.length) {
    for (var lc = 0; lc < effectMeta.lookupCandidates.length; lc++) {
      addLookupName(effectMeta.lookupCandidates[lc]);
    }
  }

  if (legacyAlias) addLookupName(legacyAlias);
  if (displayName && _normName(displayName) !== _normName(legacyAlias || "")) addLookupName(displayName);
  if (matchName && _normName(matchName) !== _normName(displayName || "")) {
    addLookupName(matchName);
  }

  for (var li = 0; li < lookupNames.length; li++) {
    effectObj = isAudioFx
      ? qe.project.getAudioEffectByName(lookupNames[li])
      : qe.project.getVideoEffectByName(lookupNames[li]);
    if (effectObj) return effectObj;
  }

  var fxList = isAudioFx
    ? qe.project.getAudioEffectList()
    : qe.project.getVideoEffectList();
  var normalTarget = _normName(displayName);
  var canonicalTarget = _canonicalEffectName(displayName);

  for (var i = 0; i < fxList.length; i++) {
    var candidate = String(fxList[i]).trim();
    var normalizedCandidate = _normName(candidate);
    var canonicalCandidate = _canonicalEffectName(candidate);
    if (normalizedCandidate === normalTarget || canonicalCandidate === canonicalTarget) {
      return isAudioFx
        ? qe.project.getAudioEffectByName(candidate)
        : qe.project.getVideoEffectByName(candidate);
    }
  }

  for (i = 0; i < fxList.length; i++) {
    candidate = String(fxList[i]).trim();
    normalizedCandidate = _normName(candidate);
    canonicalCandidate = _canonicalEffectName(candidate);
    if (
      (normalTarget && normalizedCandidate.indexOf(normalTarget) !== -1) ||
      (canonicalTarget && canonicalCandidate.indexOf(canonicalTarget) !== -1) ||
      (canonicalTarget && canonicalTarget.indexOf(canonicalCandidate) !== -1)
    ) {
      return isAudioFx
        ? qe.project.getAudioEffectByName(candidate)
        : qe.project.getVideoEffectByName(candidate);
    }
  }

  return null;
}

function _safeValueToString(value) {
  if (value === null || value === undefined) return "";
  if (value instanceof Array) return value.join(":");
  return String(value);
}

function _safeGetPropValue(prop) {
  try {
    if (prop && typeof prop.getValue === "function") {
      return _safeValueToString(prop.getValue());
    }
  } catch (e) {}
  return "";
}

function _componentSignature(comp) {
  if (!comp) return "";

  var parts = [_normName(comp.displayName)];
  try {
    if (comp.properties) {
      for (var i = 0; i < comp.properties.numItems; i++) {
        var prop = comp.properties[i];
        if (!prop) continue;
        parts.push(_normName(prop.displayName) + "=" + _safeGetPropValue(prop));
      }
    }
  } catch (e) {}
  return parts.join("|");
}

function _componentNameMatches(comp, displayName, effectMeta) {
  if (!comp) return false;

  var names = [];
  function addName(name) {
    if (!name) return;
    if (names.join("|").indexOf(String(name)) !== -1) return;
    names.push(String(name));
  }

  addName(displayName);
  if (effectMeta) {
    addName(effectMeta.displayName);
    addName(effectMeta.legacyAlias);
    addName(effectMeta.resolvedEffectName);
    if (effectMeta.lookupCandidates && effectMeta.lookupCandidates.length) {
      for (var lc = 0; lc < effectMeta.lookupCandidates.length; lc++) {
        addName(effectMeta.lookupCandidates[lc]);
      }
    }
  }

  var compNorm = _normName(comp.displayName || "");
  var compCanon = _canonicalEffectName(comp.displayName || "");
  for (var i = 0; i < names.length; i++) {
    if (_normName(names[i]) === compNorm || _canonicalEffectName(names[i]) === compCanon) {
      return true;
    }
  }
  return false;
}

function _snapshotNamedComponents(stdClip, displayName, effectMeta) {
  if (!stdClip || !stdClip.components) return [];
  var snapshots = [];
  for (var i = 0; i < stdClip.components.numItems; i++) {
    var comp = stdClip.components[i];
    if (_componentNameMatches(comp, displayName, effectMeta)) {
      snapshots.push({
        index: i,
        component: comp,
        signature: _componentSignature(comp)
      });
    }
  }
  return snapshots;
}

function _findNewlyAddedComponent(stdClip, displayName, beforeSnapshots, effectMeta) {
  var afterSnapshots = _snapshotNamedComponents(stdClip, displayName, effectMeta);
  if (afterSnapshots.length === 0) return null;
  if (beforeSnapshots.length === 0) return afterSnapshots[afterSnapshots.length - 1].component;

  var counts = {};
  var i;
  for (i = 0; i < beforeSnapshots.length; i++) {
    counts[beforeSnapshots[i].signature] = (counts[beforeSnapshots[i].signature] || 0) + 1;
  }

  for (i = 0; i < afterSnapshots.length; i++) {
    var sig = afterSnapshots[i].signature;
    if (counts[sig]) {
      counts[sig]--;
    } else {
      return afterSnapshots[i].component;
    }
  }

  return afterSnapshots[afterSnapshots.length - 1].component;
}

function _selectionTargetKey(ctx, kind) {
  if (!ctx || !ctx.stdClip) return null;
  return [
    kind,
    ctx.trackIndex,
    ctx.stdClip.name || "",
    String(ctx.stdClip.start.ticks)
  ].join("|");
}

function _findPresetTargetProp(addedEffect, param, effectMeta) {
  if (!addedEffect || !addedEffect.properties) return null;
  var isLegacy = !!(effectMeta && effectMeta.isLegacy);
  var i;
  var propCandidate;
  var targetName = param && param.name ? _normName(param.name) : "";
  var exactTargetName = param && param.name ? String(param.name) : "";

  if (isLegacy && exactTargetName) {
    for (i = 0; i < addedEffect.properties.numItems; i++) {
      propCandidate = addedEffect.properties[i];
      if (propCandidate && String(propCandidate.displayName || "") === exactTargetName) {
        return propCandidate;
      }
    }
  }

  if (targetName) {
    for (i = 0; i < addedEffect.properties.numItems; i++) {
      propCandidate = addedEffect.properties[i];
      if (propCandidate && _normName(propCandidate.displayName) === targetName) {
        return propCandidate;
      }
    }
  }

  var propIndex = parseInt(param.paramIndex, 10);
  if (!isNaN(propIndex) && propIndex >= 0 && propIndex < addedEffect.properties.numItems) {
    return addedEffect.properties[propIndex];
  }

  var pidIndex = parseInt(param.paramId, 10) - 1;
  if (!isNaN(pidIndex) && pidIndex >= 0 && pidIndex < addedEffect.properties.numItems) {
    return addedEffect.properties[pidIndex];
  }

  return null;
}

function _describeEffectProperties(effect) {
  if (!effect || !effect.properties) return "";
  var parts = [];
  for (var i = 0; i < effect.properties.numItems; i++) {
    if (!effect.properties[i]) continue;
    parts.push(i + ":" + String(effect.properties[i].displayName || ""));
  }
  return parts.join(" | ");
}

function _decodePackedColor(rawValue) {
  if (!rawValue || !/^\d{10,}$/.test(String(rawValue))) return null;

  function decimalToHex(decStr) {
    var digits = String(decStr).replace(/^0+/, "");
    if (!digits) return "0";

    var out = "";
    while (digits !== "0") {
      var quotient = "";
      var remainder = 0;

      for (var i = 0; i < digits.length; i++) {
        var num = remainder * 10 + parseInt(digits.charAt(i), 10);
        var q = Math.floor(num / 16);
        remainder = num % 16;
        if (quotient.length || q > 0) quotient += String(q);
      }

      out = remainder.toString(16).toUpperCase() + out;
      digits = quotient || "0";
    }
    return out;
  }

  try {
    var hex = decimalToHex(String(rawValue));
    while (hex.length < 16) hex = "0" + hex;
    hex = hex.substr(hex.length - 16);

    var a = parseInt(hex.substr(0, 2), 16);
    var r = parseInt(hex.substr(4, 2), 16);
    var g = parseInt(hex.substr(8, 2), 16);
    var b = parseInt(hex.substr(12, 2), 16);
    return [r / 255, g / 255, b / 255, a / 255];
  } catch (e) {
    return null;
  }
}

function _decodePackedColor16(rawValue) {
  if (!rawValue || !/^\d{10,}$/.test(String(rawValue))) return null;

  function decimalToHex(decStr) {
    var digits = String(decStr).replace(/^0+/, "");
    if (!digits) return "0";

    var out = "";
    while (digits !== "0") {
      var quotient = "";
      var remainder = 0;

      for (var i = 0; i < digits.length; i++) {
        var num = remainder * 10 + parseInt(digits.charAt(i), 10);
        var q = Math.floor(num / 16);
        remainder = num % 16;
        if (quotient.length || q > 0) quotient += String(q);
      }

      out = remainder.toString(16).toUpperCase() + out;
      digits = quotient || "0";
    }
    return out;
  }

  try {
    var hex = decimalToHex(String(rawValue));
    while (hex.length < 16) hex = "0" + hex;
    hex = hex.substr(hex.length - 16);

    var a16 = parseInt(hex.substr(0, 4), 16);
    var r16 = parseInt(hex.substr(4, 4), 16);
    var g16 = parseInt(hex.substr(8, 4), 16);
    var b16 = parseInt(hex.substr(12, 4), 16);
    return [r16 / 65535, g16 / 65535, b16 / 65535, a16 / 65535];
  } catch (e) {
    return null;
  }
}

function _packedColorMeta(rawValue) {
  if (!rawValue || !/^\d{10,}$/.test(String(rawValue))) return null;

  function decimalToHex(decStr) {
    var digits = String(decStr).replace(/^0+/, "");
    if (!digits) return "0";

    var out = "";
    while (digits !== "0") {
      var quotient = "";
      var remainder = 0;

      for (var i = 0; i < digits.length; i++) {
        var num = remainder * 10 + parseInt(digits.charAt(i), 10);
        var q = Math.floor(num / 16);
        remainder = num % 16;
        if (quotient.length || q > 0) quotient += String(q);
      }

      out = remainder.toString(16).toUpperCase() + out;
      digits = quotient || "0";
    }
    return out;
  }

  try {
    var hex = decimalToHex(String(rawValue));
    while (hex.length < 16) hex = "0" + hex;
    hex = hex.substr(hex.length - 16);

    var a8 = parseInt(hex.substr(0, 2), 16);
    var r8 = parseInt(hex.substr(4, 2), 16);
    var g8 = parseInt(hex.substr(8, 2), 16);
    var b8 = parseInt(hex.substr(12, 2), 16);

    return {
      hex16: hex,
      a8: a8,
      r8: r8,
      g8: g8,
      b8: b8,
      rgb8: ((r8 << 16) | (g8 << 8) | b8),
      bgr8: ((b8 << 16) | (g8 << 8) | r8),
      rgb8Shift8: (((r8 << 16) | (g8 << 8) | b8) << 8) >>> 0,
      bgr8Shift8: (((b8 << 16) | (g8 << 8) | r8) << 8) >>> 0,
      argb8: (((a8 << 24) >>> 0) | (r8 << 16) | (g8 << 8) | b8)
    };
  } catch (e) {
    return null;
  }
}

function _applyBooleanValue(targetProp, rawText) {
  if (rawText === "true" || rawText === "1" || rawText === "1.") {
    try { targetProp.setValue(true, true); return true; } catch (e1) {}
    try { targetProp.setValue(1, true); return true; } catch (e2) {}
  }
  if (rawText === "false" || rawText === "0" || rawText === "0.") {
    try { targetProp.setValue(false, true); return true; } catch (e3) {}
    try { targetProp.setValue(0, true); return true; } catch (e4) {}
  }
  return false;
}

function _applyLiteralParamValue(targetProp, rawValue, controlType) {
  if (rawValue === null || rawValue === undefined) return;
  var rawText = String(rawValue);
  var ctype = String(controlType || "");

  if (ctype === "6" && rawText.indexOf(":") !== -1) {
    var coords = rawText.split(":");
    if (coords.length === 2) {
      var px = parseFloat(coords[0]);
      var py = parseFloat(coords[1]);
      if (!isNaN(px) && !isNaN(py)) {
        targetProp.setValue([px, py], true);
        return;
      }
    }
  }

  if (ctype === "4" || ctype === "16" || rawText === "true" || rawText === "false") {
    if (_applyBooleanValue(targetProp, rawText)) return;
  }

  if (ctype === "7") {
    var enumVal = parseInt(rawText, 10);
    if (!isNaN(enumVal)) {
      targetProp.setValue(enumVal, true);
      return;
    }
  }

  if (ctype === "5") {
    var colorMeta = _packedColorMeta(rawText);
    if (colorMeta) {
      try {
        targetProp.setColorValue(colorMeta.a8, colorMeta.r8, colorMeta.g8, colorMeta.b8, 1);
        return;
      } catch (eSetColor) {}
      try {
        targetProp.setValue(colorMeta.rgb8, true);
        return;
      } catch (e0) {}
      try {
        targetProp.setValue(colorMeta.rgb8Shift8, true);
        return;
      } catch (e0a) {}
      try {
        targetProp.setValue(colorMeta.bgr8, true);
        return;
      } catch (e0bgr) {}
      try {
        targetProp.setValue(colorMeta.bgr8Shift8, true);
        return;
      } catch (e0bgr2) {}
      try {
        targetProp.setValue(colorMeta.argb8, true);
        return;
      } catch (e0c) {}
      try {
        targetProp.setValue("0x" + ("000000" + colorMeta.rgb8.toString(16).toUpperCase()).slice(-6), true);
        return;
      } catch (e0d) {}
    }

    var color = _decodePackedColor(rawText);
    if (color) {
      try {
        targetProp.setValue(color, true);
        return;
      } catch (e) {}
      try {
        targetProp.setColorValue(color[0], color[1], color[2], color[3], true);
        return;
      } catch (e2) {}
    }

    var color16 = _decodePackedColor16(rawText);
    if (color16) {
      try {
        targetProp.setValue(color16, true);
        return;
      } catch (e3) {}
      try {
        targetProp.setColorValue(color16[0], color16[1], color16[2], color16[3], true);
        return;
      } catch (e4) {}
      try {
        targetProp.setValue([color16[3], color16[0], color16[1], color16[2]], true);
        return;
      } catch (e4b) {}
      try {
        targetProp.setValue([color16[2], color16[1], color16[0], color16[3]], true);
        return;
      } catch (e4c) {}
    }

    try {
      targetProp.setValue(rawText, true);
      return;
    } catch (e5) {}
    var rawNum = parseFloat(rawText);
    if (!isNaN(rawNum)) {
      try {
        targetProp.setValue(rawNum, true);
        return;
      } catch (e6) {}
    }
  }

  if (rawText === "true") {
    if (_applyBooleanValue(targetProp, rawText)) return;
  }
  if (rawText === "false") {
    if (_applyBooleanValue(targetProp, rawText)) return;
  }

  if (/^\d{10,}$/.test(rawText)) {
    try {
      targetProp.setValue(rawText, true);
      return;
    } catch (e) {}
  }

  var val = parseFloat(rawText);
  if (!isNaN(val)) {
    targetProp.setValue(val, true);
    return;
  }

  targetProp.setValue(rawText, true);
}

function _buildKeyframeTimingInfo(stdClip, saved) {
  var startTicks = 0;
  var endTicks = 0;
  var inPointTicks = 0;
  var outPointTicks = 0;
  var clipName = saved && saved.clipName ? String(saved.clipName) : "";
  var projectItemName = "";
  var mediaPath = "";
  var projectItemType = "";
  var isImageLike = false;
  var isAdjustmentLike = false;

  try {
    if (stdClip && stdClip.start && stdClip.start.ticks !== undefined) {
      startTicks = Number(stdClip.start.ticks) || 0;
    }
  } catch (eStart) {}
  try {
    if (stdClip && stdClip.end && stdClip.end.ticks !== undefined) {
      endTicks = Number(stdClip.end.ticks) || 0;
    }
  } catch (eEnd) {}
  try {
    if (stdClip && stdClip.inPoint && stdClip.inPoint.ticks !== undefined) {
      inPointTicks = Number(stdClip.inPoint.ticks) || 0;
    }
  } catch (eIn) {}
  try {
    if (stdClip && stdClip.outPoint && stdClip.outPoint.ticks !== undefined) {
      outPointTicks = Number(stdClip.outPoint.ticks) || 0;
    }
  } catch (eOut) {}
  try {
    if (stdClip && stdClip.projectItem) {
      projectItemName = String(stdClip.projectItem.name || "");
      if (stdClip.projectItem.type !== undefined && stdClip.projectItem.type !== null) {
        projectItemType = String(stdClip.projectItem.type);
      }
      try {
        if (typeof stdClip.projectItem.isStill === "function" && stdClip.projectItem.isStill()) {
          isImageLike = true;
        }
      } catch (eStill) {}
      if (typeof stdClip.projectItem.getMediaPath === "function") {
        mediaPath = String(stdClip.projectItem.getMediaPath() || "");
      }
    }
  } catch (eProjectItem) {}

  if (!endTicks && saved && saved.endTicks !== undefined && saved.endTicks !== "") {
    endTicks = Number(saved.endTicks) || 0;
  }
  if (!inPointTicks && saved && saved.inPointTicks !== undefined && saved.inPointTicks !== "") {
    inPointTicks = Number(saved.inPointTicks) || 0;
  }
  if (!outPointTicks && saved && saved.outPointTicks !== undefined && saved.outPointTicks !== "") {
    outPointTicks = Number(saved.outPointTicks) || 0;
  }

  var timelineSpan = Math.max(0, endTicks - startTicks);
  var sourceSpan = Math.max(0, outPointTicks - inPointTicks);
  var labelText = (clipName + " " + projectItemName).toLowerCase();
  var mediaPathLower = mediaPath.toLowerCase();
  isAdjustmentLike = /adjustment layer/.test(labelText);
  isImageLike = !!(
    isImageLike ||
    /\.(png|jpe?g|bmp|gif|tiff?|psd|webp|heic|svg)$/i.test(mediaPathLower) ||
    /\.(png|jpe?g|bmp|gif|tiff?|psd|webp|heic|svg)$/i.test(labelText) ||
    /still image|still frame|image sequence|still\b/.test(labelText)
  );
  var useInPointOffset = !!(timelineSpan > 0 && sourceSpan > (timelineSpan * 4) && inPointTicks > 0);
  var looksLikeInfiniteStill = !!(timelineSpan > 0 && (
    isImageLike ||
    isAdjustmentLike ||
    sourceSpan > (timelineSpan * 20) ||
    (sourceSpan === 0 && inPointTicks > 0) ||
    /still|image/.test(labelText)
  ));

  return {
    startTicks: startTicks,
    endTicks: endTicks,
    inPointTicks: inPointTicks,
    outPointTicks: outPointTicks,
    timelineSpan: timelineSpan,
    sourceSpan: sourceSpan,
    useInPointOffset: useInPointOffset,
    looksLikeInfiniteStill: looksLikeInfiniteStill,
    isImageLike: isImageLike,
    isAdjustmentLike: isAdjustmentLike,
    clipName: clipName,
    projectItemName: projectItemName,
    mediaPath: mediaPath,
    projectItemType: projectItemType
  };
}

function _presetHasAnimatedParams(filterPresets) {
  if (!filterPresets || !filterPresets.length) return false;
  for (var i = 0; i < filterPresets.length; i++) {
    var params = filterPresets[i] && filterPresets[i].params ? filterPresets[i].params : [];
    for (var p = 0; p < params.length; p++) {
      if (params[p] && params[p].keyframes) return true;
    }
  }
  return false;
}

function _ensureStillImageKeyframeHelper(ctx) {
  if (!ctx || !ctx.stdClip || !ctx.qeClip) return false;

  var timingInfo = _buildKeyframeTimingInfo(ctx.stdClip, ctx.saved);
  if ((!timingInfo.isImageLike && !timingInfo.looksLikeInfiniteStill) || timingInfo.isAdjustmentLike) return false;

  var existing = _snapshotNamedComponents(ctx.stdClip, "Levels", null);
  if (existing && existing.length > 0) return true;

  var helperObj = _resolveEffectObject("Levels", "", false, null);
  if (!helperObj) return false;

  try {
    ctx.qeClip.addVideoEffect(helperObj);
    return true;
  } catch (e) {
    return false;
  }
}

function _applyPresetParams(addedEffect, params, stdClip, saved, effectMeta) {
  if (!addedEffect || !params) return;
  var timingInfo = _buildKeyframeTimingInfo(stdClip, saved);

  paramLoop: for (var p = 0; p < params.length; p++) {
    var param = params[p];
    if (param.value === null || param.value === undefined) continue paramLoop;

    var targetProp = _findPresetTargetProp(addedEffect, param, effectMeta);
    if (!targetProp) continue paramLoop;

    try {
      if (param.keyframes) {
        _applyKeyframes(targetProp, param.keyframes, param, timingInfo);
      } else {
        _applyLiteralParamValue(targetProp, param.value, param.controlType);
      }
    } catch(e) { /* ignora erro de param individual */ }
  }
}

function _normalizeAudioParamForSignature(param) {
  var name = _normName(param.name || "");
  if (name === "bypass") return null;

  var value = String(param.value === undefined || param.value === null ? "" : param.value);
  var num = parseFloat(value);
  if (!isNaN(num)) {
    value = String(Math.round(num * 1000000) / 1000000);
  }

  return [name, param.paramIndex || "", param.controlType || "", value].join("|");
}

function _filterPresetsForTarget(filterPresets, isAudioTarget) {
  var filtered = [];
  var seen = {};
  var seenEffect = {};

  for (var i = 0; i < filterPresets.length; i++) {
    var fp = filterPresets[i];
    if (!!fp.isAudio !== !!isAudioTarget) continue;

    if (!isAudioTarget) {
      filtered.push(fp);
      continue;
    }

    var effectKey = [fp.displayName, fp.matchName].join("|");
    if (seenEffect[effectKey]) continue;
    seenEffect[effectKey] = true;

    var normalizedParams = [];
    for (var p = 0; p < (fp.params || []).length; p++) {
      var normalized = _normalizeAudioParamForSignature(fp.params[p]);
      if (normalized) normalizedParams.push(normalized);
    }
    normalizedParams.sort();

    var signature = [fp.displayName, fp.matchName, normalizedParams.join("||")].join("|");
    if (seen[signature]) continue;
    seen[signature] = true;
    filtered.push(fp);
  }

  return filtered;
}

function _removeComponentIfPossible(component) {
  if (!component) return false;
  try {
    if (typeof component.remove === "function") {
      component.remove();
      return true;
    }
  } catch (e1) {}
  try {
    if (typeof component.remove === "function") {
      component.remove(true);
      return true;
    }
  } catch (e2) {}
  return false;
}

function _cleanupDuplicateAudioComponents(stdClip, displayName, keepComponent) {
  var snapshots = _snapshotNamedComponents(stdClip, displayName, null);
  if (snapshots.length <= 1) return;

  var keepIndex = -1;
  for (var i = 0; i < snapshots.length; i++) {
    if (snapshots[i].component === keepComponent) {
      keepIndex = i;
      break;
    }
  }
  if (keepIndex < 0) keepIndex = snapshots.length - 1;

  for (var j = 0; j < snapshots.length; j++) {
    if (j === keepIndex) continue;
    _removeComponentIfPossible(snapshots[j].component);
  }
}

function applyPresetWithSelection(filterPresetsJSON, selectionJSON) {
  try {
    app.enableQE();
    if (typeof qe === "undefined" || !qe.project) {
      return "Error: QE DOM não disponível.";
    }

    var selection = JSON.parse(selectionJSON);
    if (!selection || selection.length === 0) return "no_selection";

    var filterPresets = JSON.parse(filterPresetsJSON);
    if (!filterPresets || filterPresets.length === 0) return "Error: Sem dados de preset";

    var qeSequence = qe.project.getActiveSequence();
    if (!qeSequence) return "Error: Nenhuma sequência ativa.";

    var sequence = app.project.activeSequence;
    if (!sequence) return "Error: Nenhuma sequência ativa (std).";

    var applied = 0;
    var partial = 0;
    var uniqueTargets = { video: {}, audio: {} };

    for (var s = 0; s < selection.length; s++) {
      var saved = selection[s];
      var contexts = {
        video: _resolveClipContext(sequence, qeSequence, saved, false),
        audio: _resolveClipContext(sequence, qeSequence, saved, true)
      };

      var videoKey = _selectionTargetKey(contexts.video, "video");
      if (videoKey && !uniqueTargets.video[videoKey]) {
        uniqueTargets.video[videoKey] = contexts.video;
      }

      var audioKey = _selectionTargetKey(contexts.audio, "audio");
      if (audioKey && !uniqueTargets.audio[audioKey]) {
        uniqueTargets.audio[audioKey] = contexts.audio;
      }
    }

    for (var kind in uniqueTargets) {
      if (!uniqueTargets.hasOwnProperty(kind)) continue;

      for (var key in uniqueTargets[kind]) {
        if (!uniqueTargets[kind].hasOwnProperty(key)) continue;
        var ctx = uniqueTargets[kind][key];

        var targetFilterPresets = _filterPresetsForTarget(filterPresets, kind === "audio");
        if (kind === "video" && _presetHasAnimatedParams(targetFilterPresets)) {
          _ensureStillImageKeyframeHelper(ctx);
        }
        for (var f = 0; f < targetFilterPresets.length; f++) {
          var fp = targetFilterPresets[f];
          var isAudioFx = fp.isAudio;

          var effectObj = _resolveEffectObject(fp.displayName, fp.matchName, isAudioFx, fp);
          if (!effectObj) { partial++; continue; }

          var beforeSnapshots = _snapshotNamedComponents(ctx.stdClip, fp.displayName, fp);

          try {
            if (isAudioFx) {
              ctx.qeClip.addAudioEffect(effectObj);
            } else {
              ctx.qeClip.addVideoEffect(effectObj);
            }
            applied++;
          } catch (e1) {
            partial++;
            continue;
          }

          var addedEffect = _findNewlyAddedComponent(ctx.stdClip, fp.displayName, beforeSnapshots, fp);
          if (!addedEffect) {
            partial++;
            continue;
          }

          try {
            _applyPresetParams(addedEffect, fp.params, ctx.stdClip, ctx.saved, fp);
          } catch (e2) {
            partial++;
          }

          if (isAudioFx) {
            _cleanupDuplicateAudioComponents(ctx.stdClip, fp.displayName, addedEffect);
          }
        }
      }
    }

    if (applied === 0) return "no_selection";
    if (partial > 0)   return "partial";
    return "ok";

  } catch (e) {
    return "Error: " + e.message;
  }
}

// ─── Aplica keyframes a uma propriedade de efeito ─────────────────────────────

function _keyframeTimeFromTicks(ticks, originTicks, baseTicks) {
  var kfTime = new Time();
  var offsetTicks = 0;
  if (baseTicks && typeof baseTicks === "object") {
    if (baseTicks.looksLikeInfiniteStill) {
      // Synthetic clips such as stills and adjustment layers appear to key
      // against their sequence position instead of the same clip-local timing
      // path used by normal video clips.
      offsetTicks = baseTicks.startTicks || 0;
    } else {
      offsetTicks = baseTicks.inPointTicks || 0;
    }
  } else {
    offsetTicks = Number(baseTicks) || 0;
  }
  var relativeTicks = Math.max(0, Math.round((ticks - originTicks) + offsetTicks));
  kfTime.ticks = String(relativeTicks);
  try {
    kfTime.seconds = relativeTicks / 254016000000;
  } catch (e) {}
  return kfTime;
}

function _applyTemporalInterpolation(prop, time, parts) {
  if (!prop || !parts || parts.length < 3) return;

  var interpOut = 5;
  var interpIn = 5;

  if (parts.length >= 10) {
    interpOut = parseInt(parts[8], 10);
    interpIn = parseInt(parts[9], 10);
  } else if (parts.length >= 8) {
    interpOut = parseInt(parts[2], 10);
    interpIn = parseInt(parts[2], 10);
  }

  if (isNaN(interpOut)) interpOut = 5;
  if (isNaN(interpIn)) interpIn = interpOut;
  var interp = 5;

  if (interpOut === 4 && interpIn === 4) interp = 4;
  else if (interpOut === 6 || interpIn === 6 || interpOut === 7 || interpIn === 7 || interpOut === 8 || interpIn === 8) interp = 6;

  try {
    if (typeof prop.setInterpolationTypeAtKey === "function") {
      prop.setInterpolationTypeAtKey(time, interp, true);
    }
  } catch (e1) {}
}

function _clamp01(v) {
  if (isNaN(v)) return 0;
  if (v < 0) return 0;
  if (v > 1) return 1;
  return v;
}

function _parseInterpolableValue(rawText, controlType) {
  var ctype = String(controlType || "");
  if (ctype === "6" && rawText.indexOf(":") !== -1) {
    var coords = rawText.split(":");
    var px = parseFloat(coords[0]);
    var py = parseFloat(coords[1]);
    if (!isNaN(px) && !isNaN(py)) {
      return { kind: "point", x: px, y: py };
    }
    return null;
  }

  var num = parseFloat(rawText);
  if (!isNaN(num) && (ctype === "1" || ctype === "2" || ctype === "3" || ctype === "8")) {
    return { kind: "scalar", value: num };
  }

  return null;
}

function _serializeInterpolableValue(value) {
  if (!value) return "";
  if (value.kind === "point") return value.x + ":" + value.y;
  return String(value.value);
}

function _interpolateInterpolableValue(a, b, t) {
  if (!a || !b || a.kind !== b.kind) return null;
  if (a.kind === "point") {
    return {
      kind: "point",
      x: a.x + (b.x - a.x) * t,
      y: a.y + (b.y - a.y) * t
    };
  }
  return {
    kind: "scalar",
    value: a.value + (b.value - a.value) * t
  };
}

function _bezierEaseProgress(t, outInfluence, inInfluence) {
  var outInf = _clamp01((isNaN(outInfluence) ? 0.1666666667 : outInfluence));
  var inInf = _clamp01((isNaN(inInfluence) ? 0.1666666667 : inInfluence));

  // Bias helper samples toward the fast-changing part of the segment.
  var accel = Math.pow(t, Math.max(0.15, 1 - (outInf * 0.8)));
  var decel = 1 - Math.pow(1 - accel, Math.max(0.15, 1 - (inInf * 0.8)));
  return _clamp01(decel);
}

function _normalizeBezierInfluence(rawValue, fallbackValue) {
  var fallback = isNaN(fallbackValue) ? 0.1666666667 : fallbackValue;
  var value = parseFloat(rawValue);
  if (isNaN(value)) return fallback;
  if (value > 1) value = value / 100;
  return _clamp01(value);
}

function _deriveScalarBezierControls(startInfo, endInfo, startVal, endVal) {
  var defaultOutInfluence = 0.1666666667;
  var defaultInInfluence = 0.1666666667;

  var outInfluence = _normalizeBezierInfluence(
    startInfo && startInfo.parts && startInfo.parts.length > 5 ? startInfo.parts[5] : null,
    defaultOutInfluence
  );
  var inInfluence = _normalizeBezierInfluence(
    endInfo && endInfo.parts && endInfo.parts.length > 7 ? endInfo.parts[7] : null,
    defaultInInfluence
  );

  var x1 = _clamp01(outInfluence);
  var x2 = _clamp01(1 - inInfluence);

  var durationSeconds = Math.max(1 / 60, (endInfo.ticks - startInfo.ticks) / 254016000000);
  var deltaValue = endVal.value - startVal.value;
  var averageSpeed = deltaValue / durationSeconds;

  var startOutSpeed = startInfo && startInfo.parts && startInfo.parts.length > 6 ? parseFloat(startInfo.parts[6]) : NaN;
  var endInSpeed = endInfo && endInfo.parts && endInfo.parts.length > 4 ? parseFloat(endInfo.parts[4]) : NaN;

  var speedRatioOut = 1;
  var speedRatioIn = 1;
  if (!isNaN(averageSpeed) && Math.abs(averageSpeed) > 0.000001) {
    if (!isNaN(startOutSpeed)) speedRatioOut = startOutSpeed / averageSpeed;
    if (!isNaN(endInSpeed)) speedRatioIn = endInSpeed / averageSpeed;
  }

  if (!isFinite(speedRatioOut)) speedRatioOut = 1;
  if (!isFinite(speedRatioIn)) speedRatioIn = 1;

  if (speedRatioOut < 0) speedRatioOut = 0;
  if (speedRatioIn < 0) speedRatioIn = 0;

  var y1 = x1 * speedRatioOut;
  var y2 = 1 - ((1 - x2) * speedRatioIn);

  if (!isFinite(y1)) y1 = x1;
  if (!isFinite(y2)) y2 = x2;

  y1 = Math.max(-2, Math.min(3, y1));
  y2 = Math.max(-2, Math.min(3, y2));

  if (x2 < x1 + 0.02) {
    var mid = (x1 + x2) / 2;
    x1 = _clamp01(mid - 0.01);
    x2 = _clamp01(mid + 0.01);
  }

  return {
    x1: x1,
    y1: y1,
    x2: x2,
    y2: y2
  };
}

function _parsePointTangents(parts) {
  if (!parts || parts.length < 14) return null;
  var outX = parseFloat(parts[10]);
  var outY = parseFloat(parts[11]);
  var inX = parseFloat(parts[12]);
  var inY = parseFloat(parts[13]);
  if (isNaN(outX) || isNaN(outY) || isNaN(inX) || isNaN(inY)) return null;
  return {
    outX: outX,
    outY: outY,
    inX: inX,
    inY: inY
  };
}

function _cubicPoint(a, b, c, d, t) {
  var inv = 1 - t;
  return (inv * inv * inv * a) +
         (3 * inv * inv * t * b) +
         (3 * inv * t * t * c) +
         (t * t * t * d);
}

function _cubicBezierCoord(t, p0, p1, p2, p3) {
  return _cubicPoint(p0, p1, p2, p3, t);
}

function _cubicBezierDerivative(t, p0, p1, p2, p3) {
  var inv = 1 - t;
  return (3 * inv * inv * (p1 - p0)) +
         (6 * inv * t * (p2 - p1)) +
         (3 * t * t * (p3 - p2));
}

function _solveCubicBezierX(x, x1, x2) {
  var t = _clamp01(x);
  var i;

  for (i = 0; i < 6; i++) {
    var currentX = _cubicBezierCoord(t, 0, x1, x2, 1) - x;
    var slope = _cubicBezierDerivative(t, 0, x1, x2, 1);
    if (Math.abs(currentX) < 0.00001) return t;
    if (Math.abs(slope) < 0.00001) break;
    t -= currentX / slope;
    t = _clamp01(t);
  }

  var low = 0;
  var high = 1;
  for (i = 0; i < 12; i++) {
    t = (low + high) / 2;
    var bx = _cubicBezierCoord(t, 0, x1, x2, 1);
    if (Math.abs(bx - x) < 0.00001) return t;
    if (bx < x) low = t;
    else high = t;
  }

  return t;
}

function _progressBezierAt(t, x1, y1, x2, y2) {
  var solvedT = _solveCubicBezierX(t, x1, x2);
  return _clamp01(_cubicBezierCoord(solvedT, 0, y1, y2, 1));
}

function _estimatedFrameCountForSegment(startTicks, endTicks) {
  var durationTicks = Math.max(0, endTicks - startTicks);
  if (durationTicks <= 0) return 2;

  // Premiere keyframe timing in these presets aligns closely to 60fps ticks.
  var frameTicks = 4233600000;
  var estimatedFrames = Math.round(durationTicks / frameTicks);
  if (estimatedFrames < 2) estimatedFrames = 2;
  if (estimatedFrames > 120) estimatedFrames = 120;
  return estimatedFrames;
}

function _distributedSamplePosition(index, total, focusBias) {
  var t = index / total;
  var bias = focusBias || 0.65;

  if (t < 0.32) {
    return Math.pow(t / 0.32, 1.22 - (bias * 0.24)) * 0.2;
  }
  if (t < 0.62) {
    var midT = (t - 0.32) / 0.30;
    return 0.20 + (Math.pow(midT, 0.66) * 0.43);
  }

  var tailT = (t - 0.62) / 0.38;
  return 0.63 + (Math.pow(tailT, 0.88 + (bias * 0.08)) * 0.37);
}

function _deriveBezierControls(startInfo, endInfo) {
  var x1 = 0.17;
  var y1 = 0.01;
  var x2 = 0.24;
  var y2 = 1;

  if (startInfo && startInfo.parts) {
    if (startInfo.parts.length > 5) {
      var sx1 = parseFloat(startInfo.parts[5]);
      if (!isNaN(sx1)) x1 = _clamp01(0.09 + (sx1 * 0.44));
    }
    if (startInfo.parts.length > 7) {
      var sy1 = parseFloat(startInfo.parts[7]);
      if (!isNaN(sy1)) y1 = _clamp01(Math.max(0.004, sy1 * 0.04));
    }
  }

  if (endInfo && endInfo.parts) {
    if (endInfo.parts.length > 7) {
      var ex2 = parseFloat(endInfo.parts[7]);
      if (!isNaN(ex2)) x2 = _clamp01(0.15 + (ex2 * 0.18));
    }
    if (endInfo.parts.length > 5) {
      var ey2 = parseFloat(endInfo.parts[5]);
      if (!isNaN(ey2)) y2 = _clamp01(0.94 + (ey2 * 0.05));
    }
  }

  if (x1 < 0.09) x1 = 0.09;
  if (x2 < x1 + 0.04) x2 = x1 + 0.04;
  if (x2 > 0.36) x2 = 0.36;
  if (y1 > 0.04) y1 = 0.04;
  if (y2 < 0.96) y2 = 0.96;

  if (x2 < x1) {
    var mid = (x1 + x2) / 2;
    x1 = _clamp01(mid - 0.05);
    x2 = _clamp01(mid + 0.05);
  }

  return {
    x1: x1,
    y1: y1,
    x2: x2,
    y2: y2
  };
}

function _shouldEmulateBezier(partsA, partsB) {
  if (!partsA || !partsB) return false;

  var interpOut = NaN;
  var interpIn = NaN;

  if (partsA.length >= 10 && partsB.length >= 10) {
    interpOut = parseInt(partsA[8], 10);
    interpIn = parseInt(partsB[9], 10);
  } else if (partsA.length >= 8 && partsB.length >= 8) {
    interpOut = parseInt(partsA[2], 10);
    interpIn = parseInt(partsB[2], 10);
  } else {
    return false;
  }

  if (isNaN(interpOut) && isNaN(interpIn)) return false;
  if (interpOut === 4 && interpIn === 4) return false;

  return interpOut === 5 || interpIn === 5 || interpOut === 6 || interpIn === 6 ||
         interpOut === 7 || interpIn === 7 || interpOut === 8 || interpIn === 8;
}

function _seriesLooksDenseForBezierEmulation(keyInfos, controlType) {
  if (!keyInfos || keyInfos.length < 2) return false;

  var ctype = String(controlType || "");
  var frameTicks = 4233600000;
  var totalSegments = keyInfos.length - 1;
  var shortSegments = 0;
  var totalTicks = 0;

  for (var i = 0; i < totalSegments; i++) {
    var segmentTicks = Math.max(0, keyInfos[i + 1].ticks - keyInfos[i].ticks);
    totalTicks += segmentTicks;
    if (segmentTicks <= (frameTicks * 2.5)) shortSegments++;
  }

  var averageTicks = totalSegments > 0 ? (totalTicks / totalSegments) : 0;

  if (ctype === "6") {
    if (keyInfos.length >= 4) return true;
    if (shortSegments >= totalSegments && totalSegments >= 2) return true;
    return false;
  }

  if (keyInfos.length >= 7) return true;
  if (keyInfos.length >= 5 && averageTicks <= (frameTicks * 3)) return true;
  if (shortSegments >= Math.max(3, totalSegments - 1)) return true;

  return false;
}

function _emulateBezierSegment(prop, startInfo, endInfo, controlType) {
  var startVal = _parseInterpolableValue(String(startInfo.value), controlType);
  var endVal = _parseInterpolableValue(String(endInfo.value), controlType);
  if (!startVal || !endVal) return;
  if (String(controlType || "") !== "6" && startVal.kind !== "scalar") return;

  if (String(controlType || "") === "6") {
    var pointSamples = _estimatedFrameCountForSegment(startInfo.ticks, endInfo.ticks);
    var pointControls = _deriveBezierControls(startInfo, endInfo);
    for (var ps = 1; ps < pointSamples; ps++) {
      var pt = ps / pointSamples;
      var pointTicks = startInfo.ticks + ((endInfo.ticks - startInfo.ticks) * pt);
      var pointTime = _keyframeTimeFromTicks(pointTicks, startInfo.originTicks, startInfo.baseTicks);
      var pointProgress = _progressBezierAt(pt, pointControls.x1, pointControls.y1, pointControls.x2, pointControls.y2);
      var samplePoint = _interpolateInterpolableValue(startVal, endVal, pointProgress);
      if (!samplePoint) continue;

      try {
        prop.addKey(pointTime);
        _applyKeyValueAtTime(prop, _serializeInterpolableValue(samplePoint), pointTime, controlType);
        if (typeof prop.setInterpolationTypeAtKey === "function") {
          prop.setInterpolationTypeAtKey(pointTime, 0, true);
        }
      } catch (ePoint) {}
    }
    return;
  }

  var scalarControls = _deriveScalarBezierControls(startInfo, endInfo, startVal, endVal);
  var samples = _estimatedFrameCountForSegment(startInfo.ticks, endInfo.ticks);
  if (samples < 3) samples = 3;
  if (samples > 12) samples = 12;

  for (var s = 1; s < samples; s++) {
    var linearT = s / samples;
    var easedT = _progressBezierAt(
      linearT,
      scalarControls.x1,
      scalarControls.y1,
      scalarControls.x2,
      scalarControls.y2
    );
    var ticks = startInfo.ticks + ((endInfo.ticks - startInfo.ticks) * linearT);
    var helperTime = _keyframeTimeFromTicks(ticks, startInfo.originTicks, startInfo.baseTicks);
    var helperValue = _interpolateInterpolableValue(startVal, endVal, easedT);
    if (!helperValue) continue;

    try {
      prop.addKey(helperTime);
      _applyKeyValueAtTime(prop, _serializeInterpolableValue(helperValue), helperTime, controlType);
      if (typeof prop.setInterpolationTypeAtKey === "function") {
        prop.setInterpolationTypeAtKey(helperTime, 0, true);
      }
    } catch (e) {}
  }
}

function _applyKeyValueAtTime(prop, value, time, controlType) {
  var rawText = String(value);
  var ctype = String(controlType || "");

  if (ctype === "6" && rawText.indexOf(":") !== -1) {
    var coords = rawText.split(":");
    var x = parseFloat(coords[0]);
    var y = parseFloat(coords[1]);
    if (!isNaN(x) && !isNaN(y)) {
      try { prop.setValueAtKey(time, [x, y], true); return; } catch (e1) {}
      try { prop.setValueAtKey(time, x + ":" + y, true); return; } catch (e2) {}
      try { prop.setValueAtKey(time, x + "," + y, true); return; } catch (e3) {}
      try { prop.setValue([x, y], true); return; } catch (e4) {}
    }
    return;
  }

  if (ctype === "4" || ctype === "16" || rawText === "true" || rawText === "false") {
    try {
      if (rawText === "true" || rawText === "1" || rawText === "1.") {
        prop.setValueAtKey(time, true, true);
        return;
      }
      if (rawText === "false" || rawText === "0" || rawText === "0.") {
        prop.setValueAtKey(time, false, true);
        return;
      }
    } catch (eBool) {}
  }

  if (ctype === "7") {
    var enumVal = parseInt(rawText, 10);
    if (!isNaN(enumVal)) {
      prop.setValueAtKey(time, enumVal, true);
      return;
    }
  }

  if (ctype === "5") {
    var color = _decodePackedColor(rawText);
    if (color) {
      try {
        prop.setValueAtKey(time, color, true);
        return;
      } catch (eColor1) {}
    }

    var color16 = _decodePackedColor16(rawText);
    if (color16) {
      try {
        prop.setValueAtKey(time, color16, true);
        return;
      } catch (eColor2) {}
    }
  }

  var floatVal = parseFloat(rawText);
  if (!isNaN(floatVal)) {
    prop.setValueAtKey(time, floatVal, true);
  }
}

function _applyKeyframes(prop, keyframesStr, param, timingInfo) {
  try {
    prop.setTimeVarying(true);
    try {
      if (typeof prop.areKeyframesSupported === "function" && !prop.areKeyframesSupported()) {
        return;
      }
    } catch (e0) {}

    var kfEntries = keyframesStr.split(";");
    var originTicks = null;
    var startRaw = param && param.value !== undefined ? param.value : null;
    var keyInfos = [];

    if (startRaw !== null && startRaw !== undefined) {
      try {
        _applyLiteralParamValue(prop, startRaw, param ? param.controlType : null);
      } catch (eStart) {}
    }
    for (var i = 0; i < kfEntries.length; i++) {
      var entry = kfEntries[i].trim();
      if (!entry) continue;

      var parts = entry.split(",");
      if (parts.length < 2) continue;

      var ticks = parseFloat(parts[0]);
      if (isNaN(ticks)) continue;
      if (originTicks === null) {
        originTicks = ticks;
      }
      var value = parts[1].trim();
        var kfTime = _keyframeTimeFromTicks(ticks, originTicks, timingInfo);
        keyInfos.push({
          ticks: ticks,
          value: value,
          parts: parts,
          originTicks: originTicks,
          baseTicks: timingInfo || 0
        });

      try {
        prop.addKey(kfTime);
      } catch (eAdd) {
        continue;
      }
      try {
        _applyKeyValueAtTime(prop, value, kfTime, param ? param.controlType : null);
      } catch (eSet) {}
      _applyTemporalInterpolation(prop, kfTime, parts);
    }

    // Default behavior: preserve the main keyframes and apply Premiere's
    // native interpolation type only. Helper-key easing reconstruction stays
    // disabled in the stable path because it is not consistently faithful
    // across real-world presets.
  } catch(e) { /* ignora erros de keyframe */ }
}
