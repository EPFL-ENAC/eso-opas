export class EnviError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'EnviError';
  }
}


export class EnviHeaderError extends EnviError {
  constructor(message: string) {
    super(message);
    this.name = 'EnviHeaderError';
  }
}


export class EnviBilError extends EnviError {
  constructor(message: string) {
    super(message);
    this.name = 'EnviBilError';
  }
}


export class EnviImage {
  headerFile: File;
  bilFile: File;
  headerData: Record<string, string>;
  loading: Promise<void>;

  constructor(headerFile: File, bilFile: File) {
    if (!headerFile.name.toLowerCase().endsWith('.hdr')) {
      throw new EnviHeaderError('Header file must have a .hdr extension.');
    }
    if (!bilFile.name.toLowerCase().endsWith('.bil')) {
      throw new EnviBilError('BIL file must have a .bil extension.');
    }
    if (headerFile.name.slice(0, -4) !== bilFile.name.slice(0, -4)) {
      throw new EnviError('Header file and BIL file names do not match.');
    }

    this.headerFile = headerFile;
    this.bilFile = bilFile;
    this.headerData = {};

    this.loading = this.loadHeaderData().then((data) => {
      this.headerData = data;
    }).catch((e) => {
      throw e;
    });
  }

  private async loadHeaderData(): Promise<Record<string, string>> {
    const data: Record<string, string> = {};

    try {
      const text = await this.headerFile.text();
      const lines = text.split('\n');
      if (lines.length === 0) {
        throw new EnviHeaderError('Header file is empty.');
      }

      if (lines[0] !== "ENVI") {
        throw new EnviHeaderError('Invalid header file format. Should start with "ENVI".');
      }
      for (const line of lines.slice(1)) {
        const splitIndex = line.indexOf('=');
        const key = line.slice(0, splitIndex).trim();
        const value = line.slice(splitIndex + 1).trim();
        data[key] = value;
      }
    } catch (e) {
      throw new EnviHeaderError(`Failed to read header file: ${e}`);
    }

    return data;
  }

  async getBilData<T>(channels: number[], chunkIndex: number, chunkSize: number): Promise<T> {
  }
}
