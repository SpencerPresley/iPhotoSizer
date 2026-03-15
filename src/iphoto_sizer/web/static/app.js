/* iphoto-sizer Web UI — Application Logic */

(function () {
  "use strict";

  /* ===== State ===== */
  let records = [];
  let filteredRecords = [];
  let sortColumn = "size_bytes";
  let sortDirection = "desc";
  let currentPage = 1;
  let perPage = 50;
  let searchTerm = "";
  let mediaFilter = "all"; // "all" | "photo" | "video"
  let scanStats = {};

  /* ===== DOM refs ===== */
  const viewLanding = document.getElementById("view-landing");
  const viewScanning = document.getElementById("view-scanning");
  const viewResults = document.getElementById("view-results");

  const btnScan = document.getElementById("btn-scan");
  const inputMinSize = document.getElementById("input-min-size");
  const fileInput = document.getElementById("file-input");
  const fileLabel = document.getElementById("file-label");
  const btnOpenFile = document.getElementById("btn-open-file");

  const statsBar = document.getElementById("stats-bar");
  const searchInput = document.getElementById("search-input");
  const chipAll = document.getElementById("chip-all");
  const chipPhotos = document.getElementById("chip-photos");
  const chipVideos = document.getElementById("chip-videos");
  const btnExport = document.getElementById("btn-export");
  const btnNewScan = document.getElementById("btn-new-scan");

  const tableHead = document.getElementById("table-head");
  const tableBody = document.getElementById("table-body");
  const tableFooterInfo = document.getElementById("table-footer-info");
  const paginationPrev = document.getElementById("page-prev");
  const paginationNext = document.getElementById("page-next");
  const pageInfo = document.getElementById("page-info");
  const perPageSelect = document.getElementById("per-page-select");

  const modalOverlay = document.getElementById("modal-overlay");
  const modalFormats = document.getElementById("modal-formats");
  const exportFilename = document.getElementById("export-filename");
  const btnSaveExport = document.getElementById("btn-save-export");
  const btnCancelExport = document.getElementById("btn-cancel-export");
  const exportFeedback = document.getElementById("export-feedback");

  const errorBanner = document.getElementById("error-banner");
  const errorBannerText = document.getElementById("error-banner-text");

  const toast = document.getElementById("toast");

  /* ===== View management ===== */
  function showView(view) {
    viewLanding.classList.remove("active");
    viewScanning.classList.remove("active");
    viewResults.classList.remove("active");
    view.classList.add("active");
  }

  /* ===== Toast ===== */
  let toastTimer = null;
  function showToast(message, type) {
    if (toastTimer) clearTimeout(toastTimer);
    toast.textContent = message;
    toast.className = "toast " + type + " visible";
    toastTimer = setTimeout(function () {
      toast.classList.remove("visible");
    }, 3000);
  }

  /* ===== Error banner ===== */
  function showError(msg) {
    errorBannerText.textContent = msg;
    errorBanner.classList.add("visible");
  }

  function hideError() {
    errorBanner.classList.remove("visible");
  }

  /* ===== Format bytes (client side) ===== */
  function formatBytes(bytes) {
    if (bytes >= 1024 * 1024 * 1024) {
      return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GB";
    }
    return (bytes / (1024 * 1024)).toFixed(2) + " MB";
  }

  /* ===== Scan ===== */
  async function startScan() {
    var minSizeMb = parseFloat(inputMinSize.value) || 0;
    showView(viewScanning);
    hideError();

    try {
      var response = await fetch("/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ min_size_mb: minSizeMb }),
      });
      var data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Scan failed");
      }

      records = data.records;
      scanStats = {
        total_count: data.total_count,
        total_size: data.total_size,
        total_size_bytes: data.total_size_bytes,
        photo_count: data.photo_count,
        video_count: data.video_count,
        skipped_count: data.skipped_count,
      };

      showResults();
    } catch (err) {
      showView(viewLanding);
      showError(err.message);
    }
  }

  /* ===== Open file ===== */
  function openFile(file) {
    var reader = new FileReader();
    reader.onload = function (e) {
      try {
        var data = JSON.parse(e.target.result);
        var recs = [];

        // Support both array and {records: [...]} shapes
        if (Array.isArray(data)) {
          recs = data;
        } else if (data.records && Array.isArray(data.records)) {
          recs = data.records;
        } else {
          throw new Error("Unrecognized JSON structure");
        }

        records = recs;

        // Compute stats from loaded records
        var totalBytes = 0;
        var photoCount = 0;
        var videoCount = 0;
        for (var i = 0; i < records.length; i++) {
          totalBytes += records[i].size_bytes || 0;
          if (records[i].media_type === "video") {
            videoCount++;
          } else {
            photoCount++;
          }
        }
        scanStats = {
          total_count: records.length,
          total_size: formatBytes(totalBytes),
          total_size_bytes: totalBytes,
          photo_count: photoCount,
          video_count: videoCount,
          skipped_count: 0,
        };

        showResults();
      } catch (err) {
        showError("Could not parse JSON file: " + err.message);
      }
    };
    reader.readAsText(file);
  }

  /* ===== Show results ===== */
  function showResults() {
    showView(viewResults);
    renderStats();
    applyFilters();
  }

  /* ===== Stats ===== */
  function renderStats() {
    var skippedHtml = "";
    if (scanStats.skipped_count > 0) {
      skippedHtml =
        '<div class="stat-card">' +
        '<div class="stat-label">Skipped</div>' +
        '<div class="stat-value skipped">' +
        scanStats.skipped_count.toLocaleString() +
        "</div></div>";
    }

    statsBar.innerHTML =
      '<div class="stat-card">' +
      '<div class="stat-label">Total Size</div>' +
      '<div class="stat-value size">' +
      escapeHtml(scanStats.total_size) +
      "</div></div>" +
      '<div class="stat-card">' +
      '<div class="stat-label">Total Items</div>' +
      '<div class="stat-value">' +
      scanStats.total_count.toLocaleString() +
      "</div></div>" +
      '<div class="stat-card">' +
      '<div class="stat-label">Photos</div>' +
      '<div class="stat-value photo">' +
      scanStats.photo_count.toLocaleString() +
      "</div></div>" +
      '<div class="stat-card">' +
      '<div class="stat-label">Videos</div>' +
      '<div class="stat-value video">' +
      scanStats.video_count.toLocaleString() +
      "</div></div>" +
      skippedHtml;
  }

  /* ===== Filtering ===== */
  function applyFilters() {
    filteredRecords = records.filter(function (r) {
      if (mediaFilter !== "all" && r.media_type !== mediaFilter) return false;
      if (searchTerm) {
        var term = searchTerm.toLowerCase();
        var haystack = (
          r.filename +
          " " +
          r.extension +
          " " +
          r.size +
          " " +
          r.icloud_status
        ).toLowerCase();
        if (haystack.indexOf(term) === -1) return false;
      }
      return true;
    });

    applySorting();
    currentPage = 1;
    renderTable();
  }

  /* ===== Sorting ===== */
  function applySorting() {
    filteredRecords.sort(function (a, b) {
      var aVal = a[sortColumn];
      var bVal = b[sortColumn];

      // Numeric sort for size
      if (sortColumn === "size_bytes") {
        aVal = aVal || 0;
        bVal = bVal || 0;
        return sortDirection === "asc" ? aVal - bVal : bVal - aVal;
      }

      // String sort for everything else
      aVal = String(aVal || "").toLowerCase();
      bVal = String(bVal || "").toLowerCase();
      if (aVal < bVal) return sortDirection === "asc" ? -1 : 1;
      if (aVal > bVal) return sortDirection === "asc" ? 1 : -1;
      return 0;
    });
  }

  function setSort(column) {
    if (sortColumn === column) {
      sortDirection = sortDirection === "asc" ? "desc" : "asc";
    } else {
      sortColumn = column;
      sortDirection = column === "size_bytes" ? "desc" : "asc";
    }
    applySorting();
    currentPage = 1;
    renderTable();
  }

  /* ===== Render table ===== */
  var columns = [
    { key: "filename", label: "Filename" },
    { key: "extension", label: "Ext" },
    { key: "media_type", label: "Type" },
    { key: "size_bytes", label: "Size" },
    { key: "creation_date", label: "Date" },
    { key: "icloud_status", label: "iCloud" },
    { key: "_actions", label: "" },
  ];

  function renderTable() {
    // Header
    var headHtml = "<tr>";
    for (var i = 0; i < columns.length; i++) {
      var col = columns[i];
      if (col.key === "_actions") {
        headHtml += "<th></th>";
        continue;
      }
      var sortClass = "";
      if (sortColumn === col.key) {
        sortClass = sortDirection === "asc" ? " sorted-asc" : " sorted-desc";
      }
      headHtml +=
        '<th class="' +
        sortClass +
        '" data-column="' +
        col.key +
        '">' +
        col.label +
        "</th>";
    }
    headHtml += "</tr>";
    tableHead.innerHTML = headHtml;

    // Body
    var totalPages = Math.max(1, Math.ceil(filteredRecords.length / perPage));
    if (currentPage > totalPages) currentPage = totalPages;

    var start = (currentPage - 1) * perPage;
    var end = Math.min(start + perPage, filteredRecords.length);
    var pageRecords = filteredRecords.slice(start, end);

    var bodyHtml = "";
    if (pageRecords.length === 0) {
      bodyHtml =
        '<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--text-muted);">No records match your filters</td></tr>';
    } else {
      for (var j = 0; j < pageRecords.length; j++) {
        var r = pageRecords[j];
        bodyHtml += "<tr>";
        bodyHtml +=
          '<td class="cell-filename" title="' +
          escapeAttr(r.filename) +
          '">' +
          escapeHtml(r.filename) +
          "</td>";
        bodyHtml += '<td class="cell-ext">.' + escapeHtml(r.extension) + "</td>";
        bodyHtml += "<td>" + mediaBadge(r.media_type) + "</td>";
        bodyHtml += '<td class="cell-size">' + escapeHtml(r.size) + "</td>";
        bodyHtml += '<td class="cell-date">' + escapeHtml(formatDate(r.creation_date)) + "</td>";
        bodyHtml += "<td>" + icloudBadge(r.icloud_status) + "</td>";
        bodyHtml +=
          '<td><button class="btn-open" data-uuid="' +
          escapeAttr(r.uuid) +
          '">Open</button></td>';
        bodyHtml += "</tr>";
      }
    }
    tableBody.innerHTML = bodyHtml;

    // Footer
    tableFooterInfo.textContent =
      filteredRecords.length === records.length
        ? filteredRecords.length.toLocaleString() + " items"
        : filteredRecords.length.toLocaleString() +
          " of " +
          records.length.toLocaleString() +
          " items";

    pageInfo.textContent = currentPage + " / " + totalPages;
    paginationPrev.disabled = currentPage <= 1;
    paginationNext.disabled = currentPage >= totalPages;
  }

  function mediaBadge(type) {
    if (type === "video") {
      return '<span class="badge badge-video">\u25B6 Video</span>';
    }
    return '<span class="badge badge-photo">\u25CB Photo</span>';
  }

  function icloudBadge(status) {
    if (status === "cloud-only") {
      return '<span class="badge badge-cloud">\u2601 Cloud</span>';
    }
    return '<span class="badge badge-local">\u2713 Local</span>';
  }

  function formatDate(d) {
    if (!d) return "\u2014";
    // Already formatted as "YYYY-MM-DD HH:MM:SS" from backend
    return d;
  }

  function escapeHtml(str) {
    if (!str) return "";
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  function escapeAttr(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  /* ===== Open in Photos ===== */
  async function openInPhotos(uuid) {
    try {
      var response = await fetch("/open/" + encodeURIComponent(uuid), {
        method: "POST",
      });
      var data = await response.json();
      if (data.success) {
        showToast("Opened in Photos", "success");
      } else {
        showToast(data.error || "Could not open", "error");
      }
    } catch (err) {
      showToast("Failed to open: " + err.message, "error");
    }
  }

  /* ===== Export ===== */
  var selectedFormat = "csv";

  async function loadFormats() {
    try {
      var response = await fetch("/api/formats");
      var data = await response.json();
      var formats = data.formats || [];

      var html = "";
      for (var i = 0; i < formats.length; i++) {
        var cls = formats[i] === selectedFormat ? " selected" : "";
        html +=
          '<button class="format-option' +
          cls +
          '" data-format="' +
          formats[i] +
          '">' +
          formats[i].toUpperCase() +
          "</button>";
      }
      html +=
        '<button class="format-option" data-format="all">ALL</button>';
      modalFormats.innerHTML = html;
    } catch (err) {
      modalFormats.innerHTML =
        '<button class="format-option selected" data-format="csv">CSV</button>' +
        '<button class="format-option" data-format="json">JSON</button>' +
        '<button class="format-option" data-format="all">ALL</button>';
    }
  }

  function openExportModal() {
    exportFeedback.className = "export-feedback";
    exportFeedback.innerHTML = "";
    loadFormats();
    modalOverlay.classList.add("active");
  }

  function closeExportModal() {
    modalOverlay.classList.remove("active");
  }

  async function doExport() {
    btnSaveExport.disabled = true;
    btnSaveExport.textContent = "Saving...";
    exportFeedback.className = "export-feedback";
    exportFeedback.innerHTML = "";

    try {
      var response = await fetch("/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          records: records,
          format: selectedFormat,
          filename: exportFilename.value || "photos_report",
        }),
      });
      var data = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }

      var pathsHtml = "Saved successfully:";
      for (var i = 0; i < data.paths.length; i++) {
        pathsHtml += '<span class="export-path">' + escapeHtml(data.paths[i]) + "</span>";
      }
      exportFeedback.className = "export-feedback success";
      exportFeedback.innerHTML = pathsHtml;
    } catch (err) {
      exportFeedback.className = "export-feedback error";
      exportFeedback.textContent = err.message;
    } finally {
      btnSaveExport.disabled = false;
      btnSaveExport.textContent = "Save";
    }
  }

  /* ===== Event listeners ===== */

  // Scan
  btnScan.addEventListener("click", startScan);

  // File input
  fileInput.addEventListener("change", function () {
    if (fileInput.files.length > 0) {
      fileLabel.textContent = fileInput.files[0].name;
      fileLabel.classList.add("has-file");
      btnOpenFile.disabled = false;
    }
  });

  btnOpenFile.addEventListener("click", function () {
    if (fileInput.files.length > 0) {
      hideError();
      openFile(fileInput.files[0]);
    }
  });

  // Enter key on min size input
  inputMinSize.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      startScan();
    }
  });

  // Search
  searchInput.addEventListener("input", function () {
    searchTerm = searchInput.value;
    applyFilters();
  });

  // Media filter chips
  chipAll.addEventListener("click", function () {
    mediaFilter = "all";
    updateChips();
    applyFilters();
  });
  chipPhotos.addEventListener("click", function () {
    mediaFilter = "photo";
    updateChips();
    applyFilters();
  });
  chipVideos.addEventListener("click", function () {
    mediaFilter = "video";
    updateChips();
    applyFilters();
  });

  function updateChips() {
    chipAll.classList.toggle("active", mediaFilter === "all");
    chipPhotos.classList.toggle("active", mediaFilter === "photo");
    chipVideos.classList.toggle("active", mediaFilter === "video");
  }

  // Column sort (delegated)
  tableHead.addEventListener("click", function (e) {
    var th = e.target.closest("th[data-column]");
    if (th) {
      setSort(th.dataset.column);
    }
  });

  // Open in Photos (delegated)
  tableBody.addEventListener("click", function (e) {
    var btn = e.target.closest(".btn-open");
    if (btn) {
      openInPhotos(btn.dataset.uuid);
    }
  });

  // Pagination
  paginationPrev.addEventListener("click", function () {
    if (currentPage > 1) {
      currentPage--;
      renderTable();
    }
  });
  paginationNext.addEventListener("click", function () {
    var totalPages = Math.ceil(filteredRecords.length / perPage);
    if (currentPage < totalPages) {
      currentPage++;
      renderTable();
    }
  });
  perPageSelect.addEventListener("change", function () {
    perPage = parseInt(perPageSelect.value, 10);
    currentPage = 1;
    renderTable();
  });

  // Export
  btnExport.addEventListener("click", openExportModal);
  btnCancelExport.addEventListener("click", closeExportModal);
  btnSaveExport.addEventListener("click", doExport);

  modalOverlay.addEventListener("click", function (e) {
    if (e.target === modalOverlay) {
      closeExportModal();
    }
  });

  modalFormats.addEventListener("click", function (e) {
    var opt = e.target.closest(".format-option");
    if (opt) {
      selectedFormat = opt.dataset.format;
      var options = modalFormats.querySelectorAll(".format-option");
      for (var i = 0; i < options.length; i++) {
        options[i].classList.toggle("selected", options[i] === opt);
      }
    }
  });

  // New scan (back to landing)
  btnNewScan.addEventListener("click", function () {
    records = [];
    filteredRecords = [];
    searchTerm = "";
    mediaFilter = "all";
    searchInput.value = "";
    updateChips();
    hideError();
    showView(viewLanding);
  });

  // Keyboard: Escape to close modal
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && modalOverlay.classList.contains("active")) {
      closeExportModal();
    }
  });

  // Init
  showView(viewLanding);
})();
