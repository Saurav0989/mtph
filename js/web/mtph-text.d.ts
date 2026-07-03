// esbuild imports .mtph files as their raw text (see the build:web `--loader:.mtph=text`).
declare module "*.mtph" {
  const source: string;
  export default source;
}
