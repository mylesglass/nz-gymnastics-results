export interface ExportRow {
  [key: string]: unknown;
}

export interface PdfColumn {
  key: string;
  label: string;
  value: (row: ExportRow) => unknown;
  align?: "left" | "right";
}

export interface ColFormat {
  wch?: number;
  hidden?: boolean;
}

export function slugifyFilename(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
    .replace(/-+/g, "-");
}

export function downloadCSV(
  columns: string[],
  rows: ExportRow[],
  headerLabels: Record<string, string>,
  filename: string,
): void {
  const header = columns.map((c) => headerLabels[c] ?? c);
  const lines = [
    header.join(","),
    ...rows.map((r) =>
      columns
        .map((c) => {
          const v = r[c];
          const s = v == null ? "" : String(v);
          return s.includes(",") || s.includes('"') || s.includes("\n")
            ? `"${s.replace(/"/g, '""')}"`
            : s;
        })
        .join(","),
    ),
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function downloadXLSX(
  columns: string[],
  rows: ExportRow[],
  headerLabels: Record<string, string>,
  filename: string,
  colFormat?: Record<string, ColFormat>,
): Promise<void> {
  const { utils, writeFile } = await import("xlsx");
  const header = columns.map((c) => headerLabels[c] ?? c);
  const data = rows.map((r) => columns.map((c) => r[c]));
  const ws = utils.aoa_to_sheet([header, ...data]);
  if (colFormat) {
    ws["!cols"] = columns.map((c) => colFormat[c] ?? {});
  }
  const wb = utils.book_new();
  utils.book_append_sheet(wb, ws, "Results");
  writeFile(wb, filename);
}

export async function downloadPDF(
  columns: string[],
  rows: ExportRow[],
  headerLabels: Record<string, string>,
  filename: string,
  pdfColumns?: PdfColumn[],
  title?: string,
): Promise<void> {
  const [{ jsPDF }, { default: autoTable }] = await Promise.all([
    import("jspdf"),
    import("jspdf-autotable"),
  ]);
  const doc = new jsPDF({ orientation: "landscape", unit: "pt", format: "a4" });
  const cols = pdfColumns ?? columns.map((c) => ({
    key: c,
    label: headerLabels[c] ?? c,
    value: (r: ExportRow) => r[c] ?? "",
  }));
  const columnStyles: Record<string, { halign?: "left" | "right" }> = {};
  for (const c of cols) {
    if (c.align) columnStyles[c.key] = { halign: c.align };
  }
  autoTable(doc, {
    head: [cols.map((c) => c.label)],
    body: rows.map((r) => cols.map((c) => c.value(r) ?? "")),
    columnStyles,
    styles: { fontSize: 7, cellPadding: 2 },
    headStyles: { fillColor: [23, 23, 23], textColor: [255, 255, 255] },
    alternateRowStyles: { fillColor: [245, 245, 245] },
    margin: { top: title ? 55 : 30, right: 20, bottom: 40, left: 20 },
    didDrawPage: (data: { doc: typeof doc; pageNumber: number }) => {
      if (!title) return;
      data.doc.setFontSize(11);
      data.doc.setFont("helvetica", "bold");
      data.doc.setTextColor(23, 23, 23);
      data.doc.text(title, 20, 30);
      data.doc.setDrawColor(200, 200, 200);
      data.doc.line(20, 38, data.doc.internal.pageSize.getWidth() - 20, 38);
    },
  });
  const totalPages = doc.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    const width = doc.internal.pageSize.getWidth();
    const height = doc.internal.pageSize.getHeight();
    doc.setFontSize(8);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(130, 130, 130);
    doc.text(`Page ${i} of ${totalPages}`, width / 2, height - 15, { align: "center" });
  }
  doc.save(filename);
}
