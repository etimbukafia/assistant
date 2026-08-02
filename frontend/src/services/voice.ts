import { api } from "./api";
import { type DiaryCaptureScopeType, type DiaryContextEntry } from "./vault";

export async function createVoiceContextCapture(
  audioBlob: Blob,
  filename: string,
  params: {
    scope_type: DiaryCaptureScopeType;
    scope_id?: string | null;
    linked_to?: string | null;
  }
): Promise<DiaryContextEntry> {
  const form = new FormData();
  form.append("audio", audioBlob, filename);
  form.append("scope_type", params.scope_type);
  if (params.scope_id) form.append("scope_id", params.scope_id);
  if (params.linked_to) form.append("linked_to", params.linked_to);

  const response = await api.post("/context/captures/voice", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data as DiaryContextEntry;
}
