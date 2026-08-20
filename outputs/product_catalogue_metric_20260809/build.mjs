import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = "C:/PackagingEngineering/outputs/product_catalogue_metric_20260809";
const outputPath = `${outputDir}/kollipack_product_catalogue_metric.xlsx`;

const products = [
  { id: "Lamps", name: "Model 1524", l: 24, w: 21, h: 36, weight: 12, note: "Visible screenshot row" },
  { id: "Large Drum", name: "Large Drum Sample", l: 30, w: 30, h: 50, weight: 60, note: "Visible screenshot row" },
  { id: "P129472", name: "", l: 24, w: 9, h: 10, weight: 10, note: "Visible screenshot row; description blank" },
  { id: "Pallet #1", name: "UL Example 1", l: 45, w: 41, h: 55, weight: 101, note: "Visible screenshot row" },
  { id: "Pallet #2", name: "UL Example 2", l: 50, w: 42, h: 60, weight: 102, note: "Visible screenshot row" },
  { id: "Pallet #3", name: "UL Example 3", l: 48, w: 40, h: 55, weight: 103, note: "Visible screenshot row" },
  { id: "Pallet #4", name: "UL Example 4", l: 60, w: 30, h: 48, weight: 104, note: "Visible screenshot row" },
  { id: "Pallet #5", name: "UL Example 5", l: 48, w: 48, h: 50, weight: 105, note: "Visible screenshot row" },
  { id: "Potato Chips", name: "Snack Size 50 Ct.", l: 24, w: 16, h: 10, weight: 0.75, note: "Visible screenshot row" },
  { id: "Refrigerator", name: "Model 363-2", l: 32, w: 29, h: 65, weight: 87, note: "Visible screenshot row" },
  { id: "Saltines", name: "Low Fat 20 Ct.", l: 24, w: 19.5, h: 16, weight: 0.25, note: "Visible screenshot row" },
  { id: "SKU302473", name: "", l: 18, w: 11, h: 12.5, weight: 0.5, note: "Visible screenshot row; description blank" },
  { id: "SKU503739", name: "", l: 17, w: 12.55, h: 12.5, weight: 2, note: "Visible screenshot row; description blank" },
  { id: "SKU57392", name: "Case Pack 12", l: 22, w: 14.86, h: 12.5, weight: 2, note: "Visible screenshot row" },
  { id: "SKU9876", name: "Case Pack", l: 22, w: 14, h: 15, weight: 5, note: "Visible screenshot row" },
  { id: "Stereo", name: "Surround Sound", l: 29, w: 17, h: 12, weight: 21, note: "Visible screenshot row" },
  { id: "Stove", name: "5 Burner", l: 41, w: 37, h: 42, weight: 500, note: "Visible screenshot row" },
  { id: "T-20 1-1/2x60x108 Black", name: "Sheet", l: 110, w: 60, h: 1.55, weight: 13, note: "Visible screenshot row" },
  { id: "T-20 1/2x60x108 Black", name: "Sheet", l: 110, w: 60, h: 0.55, weight: 5, note: "Visible screenshot row" },
  { id: "T-20 1/2x60x108 Red/Yellow", name: "Sheet", l: 110, w: 60, h: 0.55, weight: 5, note: "Visible screenshot row" },
  { id: "T-20 1/4x60x100 Blue", name: "Sheet", l: 21, w: 21, h: 60, weight: 31, note: "Visible screenshot row; dimensions retained exactly as displayed" },
];

const workbook = Workbook.create();
const upload = workbook.worksheets.add("Product Upload");
const source = workbook.worksheets.add("Imperial Source");
const instructions = workbook.worksheets.add("Instructions");

const COLORS = {
  ink: "#15343B",
  teal: "#0B5D66",
  tealLight: "#EAF5F5",
  input: "#FFF7E6",
  formula: "#EEF6FF",
  note: "#F4F7F8",
  border: "#C7D5D8",
  white: "#FFFFFF",
  orange: "#C85A16",
};

// First worksheet: exact import headers expected by the product catalogue upload view.
upload.showGridLines = false;
upload.freezePanes.freezeRows(1);
upload.getRange("A1:J1").values = [[
  "product_id",
  "product_name",
  "product_length",
  "product_width",
  "product_height",
  "rotation_1",
  "rotation_2",
  "rotation_3",
  "weight",
  "desired_qty",
]];
upload.getRange("A1:J1").format = {
  fill: COLORS.teal,
  font: { bold: true, color: COLORS.white },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "outside", style: "medium", color: COLORS.teal },
};
upload.getRange("A1:J1").format.rowHeight = 32;

const uploadFormulas = products.map((_, index) => {
  const row = index + 2;
  const sourceRow = index + 2;
  return [
    `='Imperial Source'!A${sourceRow}`,
    `='Imperial Source'!B${sourceRow}`,
    `='Imperial Source'!C${sourceRow}*'Instructions'!$B$4`,
    `='Imperial Source'!D${sourceRow}*'Instructions'!$B$4`,
    `='Imperial Source'!E${sourceRow}*'Instructions'!$B$4`,
    `='Instructions'!$B$8`,
    `='Instructions'!$B$9`,
    `='Instructions'!$B$10`,
    `='Imperial Source'!F${sourceRow}*'Instructions'!$B$5`,
    `='Instructions'!$B$11`,
  ];
});
upload.getRange(`A2:J${products.length + 1}`).formulas = uploadFormulas;
upload.getRange(`A2:J${products.length + 1}`).format = {
  font: { color: COLORS.ink },
  verticalAlignment: "center",
  borders: { insideHorizontal: { style: "thin", color: COLORS.border }, bottom: { style: "thin", color: COLORS.border } },
};
upload.getRange(`C2:E${products.length + 1}`).format = { fill: COLORS.formula, numberFormat: "0.000", horizontalAlignment: "right" };
upload.getRange(`F2:H${products.length + 1}`).format = { fill: COLORS.formula, horizontalAlignment: "center" };
upload.getRange(`I2:I${products.length + 1}`).format = { fill: COLORS.formula, numberFormat: "0.000", horizontalAlignment: "right" };
upload.getRange(`J2:J${products.length + 1}`).format = { fill: COLORS.formula, numberFormat: "0", horizontalAlignment: "right" };
upload.getRange(`A2:B${products.length + 1}`).format.horizontalAlignment = "left";
upload.getRange("A:A").format.columnWidth = 30;
upload.getRange("B:B").format.columnWidth = 24;
upload.getRange("C:E").format.columnWidth = 15;
upload.getRange("F:H").format.columnWidth = 12;
upload.getRange("I:I").format.columnWidth = 12;
upload.getRange("J:J").format.columnWidth = 13;
upload.getRange(`A1:J${products.length + 1}`).format.rowHeight = 22;
upload.tables.add(`A1:J${products.length + 1}`, true, "ProductUploadTable");

// Second worksheet: editable source data transcribed from the screenshot.
source.showGridLines = false;
source.freezePanes.freezeRows(1);
source.getRange("A1:G1").values = [["product_id", "product_name", "length_in", "width_in", "height_in", "weight_lb", "source_note"]];
source.getRange("A1:G1").format = {
  fill: COLORS.orange,
  font: { bold: true, color: COLORS.white },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "outside", style: "medium", color: COLORS.orange },
};
source.getRange("A1:G1").format.rowHeight = 32;
source.getRange(`A2:G${products.length + 1}`).values = products.map((product) => [
  product.id,
  product.name,
  product.l,
  product.w,
  product.h,
  product.weight,
  product.note,
]);
source.getRange(`A2:G${products.length + 1}`).format = {
  fill: COLORS.input,
  font: { color: COLORS.ink },
  verticalAlignment: "center",
  borders: { insideHorizontal: { style: "thin", color: COLORS.border }, bottom: { style: "thin", color: COLORS.border } },
};
source.getRange(`C2:F${products.length + 1}`).format = { fill: COLORS.input, numberFormat: "0.00", horizontalAlignment: "right" };
source.getRange(`A2:B${products.length + 1}`).format.horizontalAlignment = "left";
source.getRange(`G2:G${products.length + 1}`).format = { fill: COLORS.note, font: { italic: true, color: COLORS.ink }, wrapText: true };
source.getRange("A:A").format.columnWidth = 30;
source.getRange("B:B").format.columnWidth = 24;
source.getRange("C:F").format.columnWidth = 14;
source.getRange("G:G").format.columnWidth = 46;
source.getRange(`A2:G${products.length + 1}`).format.rowHeight = 22;
source.getRange(`A${products.length + 1}:G${products.length + 1}`).format.rowHeight = 36;
source.tables.add(`A1:G${products.length + 1}`, true, "ImperialSourceTable");

// Third worksheet: conversion constants and upload instructions.
instructions.showGridLines = false;
instructions.getRange("A1:F1").merge();
instructions.getRange("A1").values = [["KolliPack Product Catalogue — Metric Upload Workbook"]];
instructions.getRange("A1:F1").format = {
  fill: COLORS.teal,
  font: { bold: true, color: COLORS.white, size: 16 },
  horizontalAlignment: "left",
  verticalAlignment: "center",
};
instructions.getRange("A1:F1").format.rowHeight = 30;
instructions.getRange("A3:B11").values = [
  ["Conversion / assumption", "Value"],
  ["Inches to millimetres", 25.4],
  ["Pounds to kilograms", 0.45359237],
  ["Workbook source", "Screenshot supplied by user"],
  ["Catalogue rows included", products.length],
  ["rotation_1 default", true],
  ["rotation_2 default", false],
  ["rotation_3 default", false],
  ["desired_qty default", 1],
];
instructions.getRange("A3:B3").format = {
  fill: COLORS.orange,
  font: { bold: true, color: COLORS.white },
  horizontalAlignment: "center",
  borders: { preset: "outside", style: "medium", color: COLORS.orange },
};
instructions.getRange("A4:A11").format = { fill: COLORS.note, font: { bold: true, color: COLORS.ink } };
instructions.getRange("B4:B11").format = { fill: COLORS.formula, font: { color: COLORS.ink }, horizontalAlignment: "right" };
instructions.getRange("B4:B5").format.numberFormat = "0.00000000";
instructions.getRange("B8:B10").format.horizontalAlignment = "center";
instructions.getRange("B11").format.numberFormat = "0";
instructions.getRange("A3:B11").format.borders = { preset: "all", style: "thin", color: COLORS.border };
instructions.getRange("A13:F13").merge();
instructions.getRange("A13").values = [["How to use"]];
instructions.getRange("A13:F13").format = { fill: COLORS.tealLight, font: { bold: true, color: COLORS.teal } };
instructions.getRange("A14:F18").merge(true);
instructions.getRange("A14:F18").values = [
  ["1. Use the Product Upload sheet when uploading to KolliPack. Its headers match the product catalogue Excel importer exactly."],
  ["2. To revise a product, edit the yellow cells on Imperial Source. Product Upload converts inches to mm and pounds to kg with formulas."],
  ["3. Rotation flags and desired_qty were not visible in the screenshot. They default to rotation_1=TRUE, rotation_2/3=FALSE, desired_qty=1; adjust them in Instructions if needed."],
  ["4. The final row visible at the bottom of the screenshot was partly covered by the video controls and is not included."],
  ["5. Verify product orientation, quantities, and dimensions against the source system before using the catalogue for engineering decisions."],
];
instructions.getRange("A14:F18").format = { fill: COLORS.note, font: { color: COLORS.ink }, wrapText: true, verticalAlignment: "center" };
instructions.getRange("A14:F18").format.rowHeight = 32;
instructions.getRange("A20:F20").merge();
instructions.getRange("A20").values = [["Review note: T-20 1/4x60x100 Blue is retained as 21 x 21 x 60 in because that is what is visible in the screenshot; please verify this row." ]];
instructions.getRange("A20:F20").format = { fill: "#FFF1E6", font: { bold: true, color: COLORS.orange }, wrapText: true, verticalAlignment: "center" };
instructions.getRange("A20:F20").format.rowHeight = 34;
instructions.getRange("A:A").format.columnWidth = 34;
instructions.getRange("B:B").format.columnWidth = 24;
instructions.getRange("C:F").format.columnWidth = 18;

// Make the input/formula distinction clear without modifying the upload contract.
instructions.getRange("A22:F22").merge();
instructions.getRange("A22").values = [["Legend: yellow = editable screenshot source inputs; light blue = formula-driven metric/upload values."]];
instructions.getRange("A22:F22").format = { fill: COLORS.note, font: { italic: true, color: COLORS.ink } };

await fs.mkdir(outputDir, { recursive: true });
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputPath);

const uploadCheck = await workbook.inspect({
  kind: "table",
  range: `Product Upload!A1:J${products.length + 1}`,
  include: "values,formulas",
  tableMaxRows: 5,
  tableMaxCols: 10,
});
console.log(uploadCheck.ndjson);

const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
console.log(formulaErrors.ndjson);

for (const sheetName of ["Product Upload", "Imperial Source", "Instructions"]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  const previewPath = `${outputDir}/${sheetName.replaceAll(" ", "_").toLowerCase()}_preview.png`;
  await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
  console.log(`Rendered ${previewPath}`);
}

console.log(`Saved ${outputPath}`);
