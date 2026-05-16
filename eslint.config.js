import js from "@eslint/js";
import arrayFunc from "eslint-plugin-array-func";
import eslintComments from "eslint-plugin-eslint-comments";
import jsonc from "eslint-plugin-jsonc";
import markdown from "eslint-plugin-markdown";
import noConstructorBind from "eslint-plugin-no-constructor-bind";
import noSecrets from "eslint-plugin-no-secrets";
import noUseExtendNative from "eslint-plugin-no-use-extend-native";
import optimizeRegex from "eslint-plugin-optimize-regex";
import eslintPluginPrettierRecommended from "eslint-plugin-prettier/recommended";
import promise from "eslint-plugin-promise";
import pluginSecurity from "eslint-plugin-security";
import simpleImportSort from "eslint-plugin-simple-import-sort";
import sonarjs from "eslint-plugin-sonarjs";
import switchCase from "eslint-plugin-switch-case";
import toml from "eslint-plugin-toml";
import eslintPluginUnicorn from "eslint-plugin-unicorn";
import yml from "eslint-plugin-yml";
import globals from "globals";

export default [
  {
    ignores: [
      "*~",
      "**/__pycache__",
      ".git",
      "!.circleci",
      ".mypy_cache",
      ".ruff_cache",
      ".pytest_cache",
      ".venv*",
      "dist",
      "node_modules",
      "package-lock.json",
      "test-results",
      "typings",
      "uv.lock",
    ],
  },
  {
    languageOptions: {
      globals: {
        ...globals.node,
        ...globals.browser,
        ...globals.es2024,
      },
      parserOptions: {
        ecmaFeatures: {
          impliedStrict: true,
        },
        ecmaVersion: "latest",
      },
    },
    linterOptions: {
      reportUnusedDisableDirectives: "warn",
    },
    plugins: {
      "eslint-comments": eslintComments,
      markdown,
      "no-constructor-bind": noConstructorBind,
      "no-secrets": noSecrets,
      "optimize-regex": optimizeRegex,
      security: pluginSecurity,
      "simple-import-sort": simpleImportSort,
      unicorn: eslintPluginUnicorn,
    },
    rules: {
      "array-func/prefer-array-from": "off",
      "eslint-comments/disable-enable-pair": "error",
      "eslint-comments/no-aggregating-enable": "error",
      "eslint-comments/no-duplicate-disable": "error",
      "eslint-comments/no-unlimited-disable": "error",
      "eslint-comments/no-unused-enable": "error",
      "eslint-comments/no-unused-disable": "warn",
      "max-params": ["warn", 4],
      "no-console": "warn",
      "no-debugger": "warn",
      "no-constructor-bind/no-constructor-bind": "error",
      "no-constructor-bind/no-constructor-state": "error",
      "no-secrets/no-secrets": "error",
      "optimize-regex/optimize-regex": "warn",
      "prettier/prettier": "warn",
      "security/detect-object-injection": "off",
      "simple-import-sort/exports": "warn",
      "simple-import-sort/imports": "warn",
      "space-before-function-paren": "off",
      "switch-case/newline-between-switch-case": "off",
      "unicorn/switch-case-braces": ["warn", "avoid"],
      "unicorn/prefer-node-protocol": 0,
      "unicorn/prevent-abbreviations": "off",
      "unicorn/filename-case": [
        "error",
        { case: "kebabCase", ignore: [".*.md"] },
      ],
    },
  },
  js.configs.recommended,
  arrayFunc.configs.all,
  noUseExtendNative.configs.recommended,
  promise.configs["flat/recommended"],
  sonarjs.configs.recommended,
  switchCase.configs.recommended,
  ...markdown.configs.recommended,
  pluginSecurity.configs.recommended,
  ...jsonc.configs["flat/recommended-with-jsonc"],
  ...toml.configs["flat/recommended"],
  ...yml.configs["flat/standard"],
  ...yml.configs["flat/prettier"],
  eslintPluginPrettierRecommended,
  {
    files: ["**/*.md"],
    processor: "markdown/markdown",
    rules: {
      "prettier/prettier": ["warn", { parser: "markdown" }],
    },
  },
  {
    files: ["**/*.md/*.js"],
    rules: {
      "no-unused-vars": "off",
      "no-undef": "off",
    },
  },
  {
    files: ["**/*.md/*.sh"],
    rules: {
      "prettier/prettier": ["error", { parser: "sh" }],
    },
  },
  {
    files: ["*.yaml", "*.yml"],
    rules: {
      "unicorn/filename-case": "off",
    },
  },
  {
    files: ["*.toml"],
    rules: {
      "prettier/prettier": ["error", { parser: "toml" }],
    },
  },
];
