export type UploadInitResponse = {
  sessionId: string;
  totalChunks: number;
};

export type UploadChunkResponse = {
  progress: number;
  isComplete: boolean;
};

export type UploadFinalizeResponse = {
  filename: string;
  filepath: string;
  fileSize: number;
  chunksReceived: number;
};

export type UploadCancelResponse = {
  detail: string;
};
