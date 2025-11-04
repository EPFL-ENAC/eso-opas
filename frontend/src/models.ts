export enum BilDataType {
  Uint8 = 1,
  Int16 = 2,
  Int32 = 3,
  Float = 4,
  Double = 5,
  ComplexFloat = 6,
  ComplexDouble = 9,
  Uint16 = 12,
  Uint32 = 13,
  Int64 = 14,
  Uint64 = 15,
}

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
