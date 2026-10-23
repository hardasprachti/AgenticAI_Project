import { createContext, useContext } from "react";

export interface RunControlApi {
  /** Open the run-control dialog. A no-op outside the app shell (tests, isolated pages). */
  open: () => void;
}

const RunControlContext = createContext<RunControlApi>({ open: () => {} });

export const RunControlProvider = RunControlContext.Provider;

export function useRunControl(): RunControlApi {
  return useContext(RunControlContext);
}
