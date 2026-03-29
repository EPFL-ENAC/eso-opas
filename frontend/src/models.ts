export type UploadInitResponse = {
  sessionId: string;
};

export type UploadFileResponse = {
  status: string;
};

export type ProcessResponse = {
  status: string;
  message: string;
};

export type ProcessStatusResponse = {
  status: string;
  message: string;
  output_files: string[] | null;
  progress_step: number | null;
  progress_total: number | null;
  progress_message: string | null;
};
