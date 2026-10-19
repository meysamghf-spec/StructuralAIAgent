export type PreviewKind = "image" | "pdf" | "dxf" | "text" | "none";

export function previewKind(filename: string, contentType: string | null): PreviewKind {
  const ext = filename.toLowerCase().split(".").pop() ?? "";
  if (ext === "dxf") return "dxf";
  if (ext === "pdf" || contentType === "application/pdf") return "pdf";
  if (["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(ext) || contentType?.startsWith("image/")) return "image";
  if (["txt", "csv", "json", "e2k", "f2k", "md", "s2k"].includes(ext) || contentType?.startsWith("text/")) return "text";
  return "none";
}
