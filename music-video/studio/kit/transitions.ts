import { toPresentation } from '../transitions/src/core';
import { registry } from '../transitions/src/registry';

export const transitionIds = registry.map((entry) => entry.meta.id);

const entry = (id: string) => {
  const found = registry.find((e) => e.meta.id === id);
  if (!found) throw new Error(`Unknown transition "${id}". Known: ${transitionIds.join(', ')}`);
  return found;
};

export const transitionMeta = (id: string) => entry(id).meta;

export const transitionPresentation = (id: string, params: Record<string, unknown> = {}) =>
  toPresentation(entry(id).impl, params);
