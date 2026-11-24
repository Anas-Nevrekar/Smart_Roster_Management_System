export type Weekday =
  | "Monday"
  | "Tuesday"
  | "Wednesday"
  | "Thursday"
  | "Friday"
  | "Saturday"
  | "Sunday";

export interface Timestamped {
  id: string;
  created_at: string;
  updated_at: string;
}

export interface Employee extends Timestamped {
  employee_id: string;
  full_name: string;
  email: string;
  pod_id: string | null;
  is_active: boolean;
  weekly_off_per_week: number;
  workable_days: Weekday[];
}

export interface Pod extends Timestamped {
  pod_id: string;
  pod_name: string;
  pod_lead_id: string | null;
  description: string | null;
  is_active: boolean;
}

export interface Brand extends Timestamped {
  brand_id: string;
  brand_name: string;
  description: string | null;
  is_active: boolean;
}

export interface Process extends Timestamped {
  process_id: string;
  process_name: string;
  description: string | null;
  is_active: boolean;
}

export interface Eligibility extends Timestamped {
  employee_id: string;
  brand_id: string;
  process_id: string;
  is_active: boolean;
}

export interface CoverageOverride {
  date: string;
  minimum_staffing: number;
}

export interface OperatingRule extends Timestamped {
  brand_id: string;
  brand_name?: string;
  process_id: string;
  process_name?: string;
  operating_days: Weekday[];
  public_holiday_policy: "operate" | "closed";
  minimum_staffing: number;
  coverage_overrides: CoverageOverride[];
  is_active: boolean;
}

export interface TimeOff extends Timestamped {
  time_off_id: string;
  employee_id: string;
  time_off_type: "planned_leave" | "comp_off";
  start_date: string;
  end_date: string;
  status: "pending" | "approved" | "rejected";
  reason?: string | null;
  approved_by?: string | null;
}

export interface PublicHoliday extends Timestamped {
  holiday_id?: string;
  holiday_name: string;
  holiday_date: string;
  description?: string | null;
}
