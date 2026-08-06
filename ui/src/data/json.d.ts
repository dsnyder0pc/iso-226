/**
 * JSON imports arrive untyped on purpose.
 *
 * `resolveJsonModule` would have tsc infer a literal type for web/curves.json,
 * which is ~34,000 floats -- a typecheck that should take a second takes
 * minutes. Declaring the imports as `unknown` keeps that cost at zero and
 * forces the one place that reads them, `./index.ts`, to say what shape it
 * expects rather than inheriting a shape from whatever the file happened to
 * contain on the day it was generated.
 */
declare module '*.json' {
  const value: unknown;
  export default value;
}
