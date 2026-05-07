"""Export helpers for Draw Things model index data."""

from __future__ import annotations

import csv
import html
import json
import sqlite3
from pathlib import Path

from .parse import ModelRecord


def write_json(records: list[ModelRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [record.to_dict() for record in records]
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_csv(records: list[ModelRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "name",
        "type",
        "model_family",
        "source_url",
        "huggingface_repo_id",
        "download_url",
        "author",
        "license",
        "tags",
        "sha256",
        "metadata_path",
        "likes",
        "downloads",
        "last_modified",
        "sibling_file_names",
        "readme_excerpt",
        "suggested_config_json",
        "warnings",
        "raw_metadata_json",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "id": record.id,
                    "name": record.name,
                    "type": record.type or "",
                    "model_family": record.model_family,
                    "source_url": record.source_url or "",
                    "huggingface_repo_id": record.huggingface_repo_id or "",
                    "download_url": record.download_url or "",
                    "author": record.author or "",
                    "license": record.license or "",
                    "tags": " | ".join(record.tags),
                    "sha256": record.sha256 or "",
                    "metadata_path": record.metadata_path or "",
                    "likes": record.likes if record.likes is not None else "",
                    "downloads": record.downloads if record.downloads is not None else "",
                    "last_modified": record.last_modified or "",
                    "sibling_file_names": " | ".join(record.sibling_file_names),
                    "readme_excerpt": record.readme_excerpt or "",
                    "suggested_config_json": json.dumps(record.suggested_config, sort_keys=True),
                    "warnings": " | ".join(record.warnings),
                    "raw_metadata_json": json.dumps(record.raw_metadata_json, sort_keys=True),
                }
            )


def write_sqlite(records: list[ModelRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("DROP TABLE IF EXISTS models")
        connection.execute(
            """
            CREATE TABLE models (
                id TEXT PRIMARY KEY,
                name TEXT,
                type TEXT,
                model_family TEXT,
                source_url TEXT,
                huggingface_repo_id TEXT,
                download_url TEXT,
                author TEXT,
                license TEXT,
                tags_json TEXT,
                sha256 TEXT,
                metadata_path TEXT,
                likes INTEGER,
                downloads INTEGER,
                last_modified TEXT,
                sibling_file_names_json TEXT,
                readme_excerpt TEXT,
                suggested_config_json TEXT,
                warnings_json TEXT,
                raw_metadata_json TEXT
            )
            """
        )
        for record in records:
            connection.execute(
                """
                INSERT INTO models (
                    id, name, type, model_family, source_url, huggingface_repo_id,
                    download_url, author, license, tags_json, sha256, metadata_path,
                    likes, downloads, last_modified, sibling_file_names_json,
                    readme_excerpt, suggested_config_json, warnings_json, raw_metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.name,
                    record.type,
                    record.model_family,
                    record.source_url,
                    record.huggingface_repo_id,
                    record.download_url,
                    record.author,
                    record.license,
                    json.dumps(record.tags),
                    record.sha256,
                    record.metadata_path,
                    record.likes,
                    record.downloads,
                    record.last_modified,
                    json.dumps(record.sibling_file_names),
                    record.readme_excerpt,
                    json.dumps(record.suggested_config, sort_keys=True),
                    json.dumps(record.warnings),
                    json.dumps(record.raw_metadata_json, sort_keys=True),
                ),
            )
        connection.commit()
    finally:
        connection.close()


def write_html_report(records: list[ModelRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    total_records = len(records)
    with_source = sum(1 for record in records if record.source_url)
    with_hf = sum(1 for record in records if record.huggingface_repo_id)
    with_license = sum(1 for record in records if record.license)
    with_downloads = sum(1 for record in records if record.downloads is not None)
    with_tuning = sum(
        1
        for record in records
        if isinstance(record.suggested_config.get("recommended_tuning"), dict)
        and record.suggested_config.get("recommended_tuning")
    )
    with_baseline = sum(
        1
        for record in records
        if isinstance(record.suggested_config.get("baseline_config"), dict)
        and record.suggested_config.get("baseline_config")
    )

    families = sorted({record.model_family for record in records if record.model_family})
    types = sorted({record.type or "unknown" for record in records})
    licenses = sorted({record.license or "unknown" for record in records})
    scale_values = sorted(
        {
            str(record.suggested_config.get("baseline_config", {}).get("default_scale"))
            for record in records
            if record.suggested_config.get("baseline_config", {}).get("default_scale") is not None
        },
        key=int,
    )

    rows = []
    for record in records:
        baseline_config = record.suggested_config.get("baseline_config", {})
        recommended_tuning = record.suggested_config.get("recommended_tuning", {})
        tags_text = ", ".join(record.tags)
        default_scale = baseline_config.get("default_scale")
        guidance_embed = baseline_config.get("guidance_embed")
        hires_fix_scale = baseline_config.get("hires_fix_scale")
        config_bits = []
        if default_scale is not None:
            config_bits.append(f"scale {default_scale}")
        if hires_fix_scale is not None:
            config_bits.append(f"hires {hires_fix_scale}")
        if guidance_embed is True:
            config_bits.append("guidance embed")
        elif guidance_embed is False:
            config_bits.append("no guidance embed")
        rows.append(
            {
                "id": record.id,
                "name": record.name,
                "model_family": record.model_family,
                "type": record.type or "",
                "author": record.author or "",
                "license": record.license or "",
                "downloads": "" if record.downloads is None else str(record.downloads),
                "downloads_sort": -1 if record.downloads is None else record.downloads,
                "last_modified": record.last_modified or "",
                "source_kind": "hf" if record.huggingface_repo_id else ("url" if record.source_url else ""),
                "has_tuning": "yes" if recommended_tuning else "",
                "has_baseline": "yes" if baseline_config else "",
                "default_scale": "" if default_scale is None else str(default_scale),
                "guidance_embed": "" if guidance_embed is None else ("yes" if guidance_embed else "no"),
                "config_summary": ", ".join(config_bits),
                "warning_count": len(record.warnings),
                "search_blob": " ".join(
                    part
                    for part in [
                        record.id,
                        record.name,
                        record.model_family,
                        record.type or "",
                        record.author or "",
                        record.license or "",
                        tags_text,
                        ", ".join(config_bits),
                    ]
                    if part
                ).lower(),
                "detail_json": json.dumps(
                    {
                        "id": record.id,
                        "name": record.name,
                        "family": record.model_family,
                        "type": record.type,
                        "author": record.author,
                        "license": record.license,
                        "source_url": record.source_url,
                        "huggingface_repo_id": record.huggingface_repo_id,
                        "download_url": record.download_url,
                        "sha256": record.sha256,
                        "metadata_path": record.metadata_path,
                        "tags": record.tags,
                        "likes": record.likes,
                        "downloads": record.downloads,
                        "last_modified": record.last_modified,
                        "baseline_config": baseline_config,
                        "recommended_tuning": recommended_tuning,
                        "warnings": record.warnings,
                        "readme_excerpt": record.readme_excerpt,
                    },
                    sort_keys=True,
                ),
            }
        )

    html_rows = "\n".join(
        (
            "<tr "
            f"data-family='{html.escape(row['model_family'])}' "
            f"data-type='{html.escape(row['type'])}' "
            f"data-license='{html.escape(row['license'])}' "
            f"data-source='{html.escape(row['source_kind'])}' "
            f"data-tuning='{html.escape(row['has_tuning'])}' "
            f"data-baseline='{html.escape(row['has_baseline'])}' "
            f"data-scale='{html.escape(row['default_scale'])}' "
            f"data-guidance='{html.escape(row['guidance_embed'])}' "
            f"data-search='{html.escape(row['search_blob'])}' "
            f"data-detail='{html.escape(row['detail_json'])}'"
            ">"
            f"<td>{html.escape(row['id'])}</td>"
            f"<td><div>{html.escape(row['name'])}</div><div class='mini'>{html.escape(row['config_summary'])}</div></td>"
            f"<td>{html.escape(row['model_family'])}</td>"
            f"<td>{html.escape(row['type'])}</td>"
            f"<td>{html.escape(row['author'])}</td>"
            f"<td>{html.escape(row['license'])}</td>"
            f"<td>{html.escape(row['source_kind'])}</td>"
            f"<td data-sort='{row['downloads_sort']}'>{html.escape(row['downloads'])}</td>"
            f"<td>{html.escape(row['last_modified'])}</td>"
            "</tr>"
        )
        for row in rows
    )

    family_options = "\n".join(
        f"<option value='{html.escape(value)}'>{html.escape(value)}</option>" for value in families
    )
    type_options = "\n".join(
        f"<option value='{html.escape(value)}'>{html.escape(value)}</option>" for value in types
    )
    license_options = "\n".join(
        f"<option value='{html.escape(value)}'>{html.escape(value)}</option>" for value in licenses
    )
    scale_options = "\n".join(
        f"<option value='{html.escape(value)}'>{html.escape(value)}</option>" for value in scale_values
    )

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Draw Things Uncurated Model Report</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f2ea;
      --panel: #fffaf1;
      --accent: #2f5d50;
      --accent-2: #b55d34;
      --text: #1f1f1f;
      --muted: #6e6a62;
      --border: #d9d0c2;
      --chip: #f1e7d7;
    }}
    body {{
      margin: 0;
      padding: 24px;
      font-family: "Iowan Old Style", Georgia, serif;
      background: radial-gradient(circle at top, #fff6df 0%, var(--bg) 50%, #efe8dc 100%);
      color: var(--text);
    }}
    .shell {{
      max-width: 1440px;
      margin: 0 auto;
      background: rgba(255, 250, 241, 0.92);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 24px;
      box-shadow: 0 18px 48px rgba(63, 48, 25, 0.08);
      backdrop-filter: blur(12px);
    }}
    h1 {{
      margin-top: 0;
      font-size: 2.2rem;
      color: var(--accent);
    }}
    .hero {{
      display: grid;
      grid-template-columns: 1.3fr 1fr;
      gap: 18px;
      margin-bottom: 18px;
    }}
    .hero-copy {{
      padding: 18px;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: linear-gradient(145deg, rgba(255,255,255,0.95), rgba(247,239,224,0.9));
    }}
    .hero-copy p {{
      margin: 0.5rem 0 0;
      color: var(--muted);
      line-height: 1.5;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .stat {{
      padding: 16px;
      border-radius: 16px;
      background: linear-gradient(165deg, #fff, #f7efdf);
      border: 1px solid var(--border);
    }}
    .stat strong {{
      display: block;
      font-size: 1.8rem;
      color: var(--accent);
    }}
    .stat span {{
      color: var(--muted);
      font-size: 0.95rem;
    }}
    .controls {{
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}
    input, select {{
      width: 100%;
      box-sizing: border-box;
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: white;
      font-size: 1rem;
    }}
    .full {{
      grid-column: 1 / -1;
    }}
    .toolbar {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 18px;
    }}
    .chip {{
      border: 1px solid var(--border);
      background: var(--chip);
      color: var(--text);
      padding: 8px 12px;
      border-radius: 999px;
      font-size: 0.92rem;
      cursor: pointer;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.8fr);
      gap: 18px;
      align-items: start;
    }}
    .panel {{
      border: 1px solid var(--border);
      border-radius: 16px;
      background: rgba(255,255,255,0.84);
      overflow: hidden;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: white;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid #eee5d8;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #f3ecdf;
      cursor: pointer;
      position: sticky;
      top: 0;
      z-index: 1;
    }}
    tr:nth-child(even) td {{
      background: #fffdfa;
    }}
    tr.is-hidden {{
      display: none;
    }}
    tr.is-selected td {{
      background: #e9f1ea;
    }}
    .mini {{
      margin-top: 4px;
      color: var(--muted);
      font-size: 0.82rem;
      line-height: 1.35;
    }}
    .detail {{
      padding: 18px;
    }}
    .detail h2 {{
      margin: 0 0 6px;
      color: var(--accent);
      font-size: 1.4rem;
    }}
    .detail .meta {{
      color: var(--muted);
      margin-bottom: 16px;
    }}
    .detail-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px 14px;
      margin-bottom: 18px;
    }}
    .detail-grid div {{
      padding: 10px 12px;
      border-radius: 12px;
      background: #fffdfa;
      border: 1px solid #eee5d8;
    }}
    .detail-grid strong {{
      display: block;
      font-size: 0.8rem;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 4px;
    }}
    .config-block {{
      margin-bottom: 14px;
      padding: 14px;
      border-radius: 14px;
      border: 1px solid var(--border);
      background: linear-gradient(180deg, #fff, #faf4e9);
    }}
    .config-block h3 {{
      margin: 0 0 8px;
      color: var(--accent-2);
      font-size: 1rem;
    }}
    .config-block pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 0.9rem;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    .excerpt {{
      color: var(--muted);
      line-height: 1.5;
      margin: 0;
    }}
    .note {{
      color: var(--muted);
      margin-bottom: 16px;
    }}
    @media (max-width: 800px) {{
      body {{ padding: 12px; }}
      .shell {{ padding: 16px; }}
      .hero, .layout {{ grid-template-columns: 1fr; }}
      .stats {{ grid-template-columns: 1fr 1fr; }}
      .controls {{ grid-template-columns: 1fr 1fr; }}
      .detail-grid {{ grid-template-columns: 1fr; }}
      th, td {{ font-size: 0.9rem; padding: 8px; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <div class="hero">
      <div class="hero-copy">
        <h1>Draw Things Uncurated Model Report</h1>
        <p>Inspect the local uncurated index with sortable tables, fast filters, and an inline detail panel for baseline config and recommended tuning hints.</p>
      </div>
      <div class="stats">
        <div class="stat"><strong>{total_records}</strong><span>Total Records</span></div>
        <div class="stat"><strong>{with_source}</strong><span>With Source URL</span></div>
        <div class="stat"><strong>{with_hf}</strong><span>With Hugging Face Repo</span></div>
        <div class="stat"><strong>{with_license}</strong><span>With License</span></div>
        <div class="stat"><strong>{with_downloads}</strong><span>With Downloads</span></div>
        <div class="stat"><strong>{with_baseline}</strong><span>With Baseline Config</span></div>
        <div class="stat"><strong>{with_tuning}</strong><span>With Tuning Hints</span></div>
      </div>
    </div>
    <p class="note">Click a row to inspect it. Click a column header to sort. Combine the filters to zero in on useful models quickly.</p>
    <div class="controls">
      <input class="full" id="filter" placeholder="Filter by id, name, family, type, author, license, tags..." />
      <select id="family-filter">
        <option value="">All Families</option>
        {family_options}
      </select>
      <select id="type-filter">
        <option value="">All Types</option>
        {type_options}
      </select>
      <select id="license-filter">
        <option value="">All Licenses</option>
        {license_options}
      </select>
      <select id="source-filter">
        <option value="">Any Source</option>
        <option value="hf">Hugging Face</option>
        <option value="url">Other URL</option>
        <option value="none">No Source</option>
      </select>
      <select id="scale-filter">
        <option value="">Any Default Scale</option>
        {scale_options}
      </select>
      <select id="guidance-filter">
        <option value="">Any Guidance Embed</option>
        <option value="yes">Guidance Embed</option>
        <option value="no">No Guidance Embed</option>
      </select>
      <select id="tuning-filter">
        <option value="">Any Tuning Hints</option>
        <option value="yes">Has Recommended Tuning</option>
        <option value="no">Baseline Only</option>
      </select>
    </div>
    <div class="toolbar">
      <button class="chip" data-preset="hf">Hugging Face Only</button>
      <button class="chip" data-preset="downloads">Has Downloads</button>
      <button class="chip" data-preset="flux16">Flux @ Scale 16</button>
      <button class="chip" data-preset="guidance">Guidance Embed</button>
      <button class="chip" data-preset="license">Has License</button>
      <button class="chip" data-preset="tuning">Has Tuning Hints</button>
      <button class="chip" data-preset="reset">Reset Filters</button>
      <span class="chip" id="visible-count">Visible: {total_records}</span>
    </div>
    <div class="layout">
      <div class="panel">
        <table id="models-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Model Family</th>
              <th>Type</th>
              <th>Author</th>
              <th>License</th>
              <th>Source</th>
              <th>Downloads</th>
              <th>Last Modified</th>
            </tr>
          </thead>
          <tbody>
            {html_rows}
          </tbody>
        </table>
      </div>
      <aside class="panel">
        <div class="detail" id="detail-panel">
          <h2>Select A Model</h2>
          <p class="meta">Pick a row from the table to inspect its source links, config hints, and metadata summary.</p>
        </div>
      </aside>
    </div>
  </div>
  <script>
    const table = document.getElementById("models-table");
    const tbody = table.querySelector("tbody");
    const filter = document.getElementById("filter");
    const familyFilter = document.getElementById("family-filter");
    const typeFilter = document.getElementById("type-filter");
    const licenseFilter = document.getElementById("license-filter");
    const sourceFilter = document.getElementById("source-filter");
    const scaleFilter = document.getElementById("scale-filter");
    const guidanceFilter = document.getElementById("guidance-filter");
    const tuningFilter = document.getElementById("tuning-filter");
    const detailPanel = document.getElementById("detail-panel");
    const visibleCount = document.getElementById("visible-count");
    let sortState = {{ index: 0, asc: true }};

    function sortRows(index) {{
      const rows = Array.from(tbody.querySelectorAll("tr"));
      const asc = sortState.index === index ? !sortState.asc : true;
      sortState = {{ index, asc }};
      rows.sort((a, b) => {{
        const aCell = a.children[index];
        const bCell = b.children[index];
        const aValue = (aCell.dataset.sort || aCell.textContent).trim().toLowerCase();
        const bValue = (bCell.dataset.sort || bCell.textContent).trim().toLowerCase();
        const aNum = Number(aValue);
        const bNum = Number(bValue);
        const numeric = !Number.isNaN(aNum) && !Number.isNaN(bNum) && aValue !== "" && bValue !== "";
        if (numeric) {{
          return asc ? aNum - bNum : bNum - aNum;
        }}
        return asc ? aValue.localeCompare(bValue) : bValue.localeCompare(aValue);
      }});
      tbody.replaceChildren(...rows);
    }}

    function renderConfigBlock(title, value) {{
      if (!value || (typeof value === "object" && Object.keys(value).length === 0)) {{
        return "";
      }}
      return `<div class="config-block"><h3>${{title}}</h3><pre>${{JSON.stringify(value, null, 2)}}</pre></div>`;
    }}

    function renderDetail(row) {{
      const detail = JSON.parse(row.dataset.detail);
      detailPanel.innerHTML = `
        <h2>${{detail.name || detail.id}}</h2>
        <p class="meta">${{detail.id}} · ${{detail.family || ""}}${{detail.type ? " · " + detail.type : ""}}</p>
        <div class="detail-grid">
          <div><strong>Author</strong>${{detail.author || "Unknown"}}</div>
          <div><strong>License</strong>${{detail.license || "Unknown"}}</div>
          <div><strong>Downloads</strong>${{detail.downloads ?? "N/A"}}</div>
          <div><strong>Likes</strong>${{detail.likes ?? "N/A"}}</div>
          <div><strong>Source URL</strong>${{detail.source_url || "None"}}</div>
          <div><strong>HF Repo</strong>${{detail.huggingface_repo_id || "None"}}</div>
          <div><strong>SHA256</strong>${{detail.sha256 || "None"}}</div>
          <div><strong>Metadata Path</strong>${{detail.metadata_path || "None"}}</div>
        </div>
        ${{renderConfigBlock("Baseline Config", detail.baseline_config)}}
        ${{renderConfigBlock("Recommended Tuning", detail.recommended_tuning)}}
        <div class="config-block">
          <h3>Tags</h3>
          <pre>${{(detail.tags || []).join(", ") || "None"}}</pre>
        </div>
        <div class="config-block">
          <h3>Warnings</h3>
          <pre>${{(detail.warnings || []).join("\\n") || "None"}}</pre>
        </div>
        <div class="config-block">
          <h3>README Excerpt</h3>
          <p class="excerpt">${{detail.readme_excerpt || "No excerpt available."}}</p>
        </div>
      `;
    }}

    function applyFilters() {{
      const query = filter.value.trim().toLowerCase();
      const family = familyFilter.value;
      const type = typeFilter.value;
      const license = licenseFilter.value;
      const source = sourceFilter.value;
      const scale = scaleFilter.value;
      const guidance = guidanceFilter.value;
      const tuning = tuningFilter.value;
      let visible = 0;

      Array.from(tbody.querySelectorAll("tr")).forEach((row) => {{
        const matchesQuery = !query || row.dataset.search.includes(query);
        const matchesFamily = !family || row.dataset.family === family;
        const matchesType = !type || row.dataset.type === type;
        const matchesLicense = !license || row.dataset.license === license;
        const sourceKind = row.dataset.source || "";
        const matchesSource = !source || (source === "none" ? !sourceKind : sourceKind === source);
        const matchesScale = !scale || row.dataset.scale === scale;
        const matchesGuidance = !guidance || row.dataset.guidance === guidance;
        const hasTuning = row.dataset.tuning === "yes";
        const matchesTuning = !tuning || (tuning === "yes" ? hasTuning : !hasTuning);
        const show = matchesQuery && matchesFamily && matchesType && matchesLicense && matchesSource && matchesScale && matchesGuidance && matchesTuning;
        row.classList.toggle("is-hidden", !show);
        if (show) {{
          visible += 1;
        }}
      }});

      visibleCount.textContent = `Visible: ${{visible}}`;
    }}

    Array.from(table.querySelectorAll("th")).forEach((th, index) => {{
      th.addEventListener("click", () => sortRows(index));
    }});

    Array.from(tbody.querySelectorAll("tr")).forEach((row) => {{
      row.addEventListener("click", () => {{
        Array.from(tbody.querySelectorAll("tr")).forEach((candidate) => candidate.classList.remove("is-selected"));
        row.classList.add("is-selected");
        renderDetail(row);
      }});
    }});

    [filter, familyFilter, typeFilter, licenseFilter, sourceFilter, scaleFilter, guidanceFilter, tuningFilter].forEach((element) => {{
      element.addEventListener("input", applyFilters);
      element.addEventListener("change", applyFilters);
    }});

    Array.from(document.querySelectorAll("[data-preset]")).forEach((button) => {{
      button.addEventListener("click", () => {{
        const preset = button.dataset.preset;
        filter.value = "";
        familyFilter.value = "";
        typeFilter.value = "";
        licenseFilter.value = "";
        sourceFilter.value = "";
        scaleFilter.value = "";
        guidanceFilter.value = "";
        tuningFilter.value = "";
        if (preset === "hf") {{
          sourceFilter.value = "hf";
        }} else if (preset === "downloads") {{
          filter.value = "downloads";
        }} else if (preset === "flux16") {{
          familyFilter.value = "Flux";
          scaleFilter.value = "16";
        }} else if (preset === "guidance") {{
          guidanceFilter.value = "yes";
        }} else if (preset === "license") {{
          filter.value = "";
        }} else if (preset === "tuning") {{
          tuningFilter.value = "yes";
        }}
        if (preset === "downloads") {{
          Array.from(tbody.querySelectorAll("tr")).forEach((row) => {{
            row.classList.toggle("is-hidden", Number(row.children[7].dataset.sort || -1) < 0);
          }});
          const visible = Array.from(tbody.querySelectorAll("tr")).filter((row) => !row.classList.contains("is-hidden")).length;
          visibleCount.textContent = `Visible: ${{visible}}`;
          return;
        }}
        if (preset === "license") {{
          Array.from(tbody.querySelectorAll("tr")).forEach((row) => {{
            row.classList.toggle("is-hidden", !row.dataset.license);
          }});
          const visible = Array.from(tbody.querySelectorAll("tr")).filter((row) => !row.classList.contains("is-hidden")).length;
          visibleCount.textContent = `Visible: ${{visible}}`;
          return;
        }}
        applyFilters();
      }});
    }});

    const firstVisibleRow = tbody.querySelector("tr");
    if (firstVisibleRow) {{
      firstVisibleRow.classList.add("is-selected");
      renderDetail(firstVisibleRow);
    }}
  </script>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")
