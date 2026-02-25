import { api } from "./api";

export interface ConnectMicrosoftRequest {
  provider_token: string;
  provider_refresh_token?: string | null;
  email: string;
}

export interface ConnectMicrosoftResponse {
  status: string;
  message: string;
  email: string;
}

export async function connectMicrosoft(
  request: ConnectMicrosoftRequest,
  accessToken?: string
): Promise<ConnectMicrosoftResponse> {
  const config = accessToken
    ? { headers: { Authorization: `Bearer ${accessToken}` } }
    : {};
  const response = await api.post<ConnectMicrosoftResponse>(
    "/auth/microsoft/connect",
    request,
    config
  );
  return response.data;
}

export async function disconnectProvider(
  provider?: "google" | "microsoft"
): Promise<{ status: string; message: string }> {
  const response = await api.post<{ status: string; message: string }>(
    "/auth/provider/disconnect",
    provider ? { provider } : {}
  );
  return response.data;
}
