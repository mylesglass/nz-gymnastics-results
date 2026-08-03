<script lang="ts">
  import type { ColFormat, ExportRow, PdfColumn } from "$lib/export";
  import { downloadCSV, downloadXLSX, downloadPDF, slugifyFilename } from "$lib/export";

  let {
    columns,
    rows,
    headerLabels,
    filename,
    label = "Export",
    pdfColumns,
    title,
    colFormat,
  }: {
    columns: string[];
    rows: ExportRow[];
    headerLabels: Record<string, string>;
    filename: string;
    label?: string;
    pdfColumns?: PdfColumn[];
    title?: string;
    colFormat?: Record<string, ColFormat>;
  } = $props();

  let exporting = $state("");

  async function handle(format: "csv" | "xlsx" | "pdf") {
    exporting = format;
    const base = slugifyFilename(filename);
    try {
      if (format === "csv") downloadCSV(columns, rows, headerLabels, `${base}.csv`);
      else if (format === "xlsx") await downloadXLSX(columns, rows, headerLabels, `${base}.xlsx`, colFormat);
      else await downloadPDF(columns, rows, headerLabels, `${base}.pdf`, pdfColumns, title);
    } catch {
      // ignore export failures
    } finally {
      exporting = "";
    }
  }
</script>

<div class="dropdown dropdown-end ml-auto">
  <button class="btn btn-secondary btn-sm" type="button" disabled={exporting !== ""}>
    {#if exporting}<span class="loading loading-spinner loading-xs"></span>{/if}
    {label} ▾
  </button>
  <ul tabindex="0" class="dropdown-content menu bg-base-100 rounded-box w-40 p-2 shadow z-50" style="z-index: 50">
    <li><button type="button" class="justify-between" onclick={() => handle("csv")} disabled={exporting !== ""}>CSV</button></li>
    <li><button type="button" class="justify-between" onclick={() => handle("xlsx")} disabled={exporting !== ""}>XLSX</button></li>
    <li><button type="button" class="justify-between" onclick={() => handle("pdf")} disabled={exporting !== ""}>PDF</button></li>
  </ul>
</div>
