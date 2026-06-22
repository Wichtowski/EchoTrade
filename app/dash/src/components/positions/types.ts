import type { Broker, Currency, Sector } from "../../lib/api";

export type PositionFormState = {
  account_type: string;
  ticker: string;
  quantity: string;
  average_price: string;
  broker: Broker;
  currency: Currency;
  sector: Sector;
  thesis: string;
  opened_at: string;
};

export type TradeFormState = {
  account_type: string;
  ticker: string;
  action: "BUY" | "SELL";
  quantity: string;
  price: string;
  broker: Broker;
  currency: Currency;
  fees: string;
  sector: Sector;
  thesis: string;
  notes: string;
  executed_at: string;
  review_date: string;
};

export type PlanFormState = {
  account_type: string;
  name: string;
  broker: Broker;
  currency: Currency;
  monthly_amount: string;
  contribution_day: string;
  start_date: string;
  notes: string;
};

export type PlanTargetFormState = {
  plan_id: string;
  ticker: string;
  currency: Currency;
  weight_pct: string;
  sector: Sector;
  composition_sectors: string[];
  notes: string;
};

export type PlanPauseFormState = {
  plan_id: string;
  start_date: string;
  end_date: string;
  reason: string;
};

export type PlanAmountChangeFormState = {
  plan_id: string;
  effective_date: string;
  monthly_amount: string;
  note: string;
};

export type PlanOneOffContributionFormState = {
  plan_id: string;
  contribution_date: string;
  amount: string;
  note: string;
};
