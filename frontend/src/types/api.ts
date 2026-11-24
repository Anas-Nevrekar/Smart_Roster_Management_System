export interface ApiSuccess<T> {
  success: true;
  data: T;
}

export interface ApiList<T> {
  success: true;
  data: T[];
  total: number;
}

export interface ApiErrorBody {
  success: false;
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export interface ApiHealth {
  status: string;
  application: string;
  version: string;
}

export interface ApiReadiness {
  status: string;
  external_persistence: boolean;
}
