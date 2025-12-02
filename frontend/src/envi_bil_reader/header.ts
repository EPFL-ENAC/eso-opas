export class ENVIHeaderError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ENVIHeaderError';
  }
}

export async function loadHeaderData(file: File): Promise<Record<string, string>> {
  const data: Record<string, string> = {};

  try {
    const text = await file.text();
    const lines = text.split('\n');
    if (lines.length === 0) {
      throw new ENVIHeaderError('Header file is empty.');
    }

    if (lines[0] !== "ENVI") {
      throw new ENVIHeaderError('Invalid header file format. Should start with "ENVI".');
    }
    for (const line of lines.slice(1)) {
      const splitIndex = line.indexOf('=');
      const key = line.slice(0, splitIndex).trim();
      const value = line.slice(splitIndex + 1).trim();
      data[key] = value;
    }
  } catch (e) {
    throw new ENVIHeaderError(`Failed to read header file: ${e}`);
  }

  return data;
}
