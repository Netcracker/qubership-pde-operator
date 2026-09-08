const path = require("path");
const { merge } = require("webpack-merge");
const webpack = require("webpack");
const common = require("./webpack.common.cjs");

/** React 19 Argo exposes ReactJSXRuntime; React 16 hosts get createElement fallback. */
const JSX_RUNTIME_BANNER = "window.__PDE_JSX_RUNTIME__=window.ReactJSXRuntime||(function(){var R=window.React;if(!R){return{Fragment:function(){return null},jsx:function(){return null},jsxs:function(){return null}};};return{Fragment:R.Fragment,jsx:R.createElement,jsxs:R.createElement};})();";

/** @type {import('webpack').Configuration} */
module.exports = merge(common, {
  mode: "production",
  entry: "./src/entries/extension.tsx",
  output: {
    path: path.resolve(__dirname, "dist"),
    filename: "extension-pde-argo-extension.js",
    iife: true,
    globalObject: "globalThis",
  },
  externals: {
    react: "React",
    "react-dom": "ReactDOM",
    "react/jsx-runtime": "__PDE_JSX_RUNTIME__",
    "react/jsx-dev-runtime": "__PDE_JSX_RUNTIME__",
  },
  externalsType: "window",
  module: {
    rules: [
      {
        test: /\.css$/,
        use: [{ loader: "css-loader", options: { exportType: "string" } }],
      },
    ],
  },
  optimization: {
    splitChunks: false,
    runtimeChunk: false,
  },
  plugins: [
    new webpack.BannerPlugin({
      banner: JSX_RUNTIME_BANNER,
      raw: true,
      entryOnly: true,
    }),
  ],
});
