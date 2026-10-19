-- Seed the capability catalog used by the Assistant Builder (it was empty on a fresh database,
-- so no assistant could pass validation). Idempotent.
INSERT INTO agent_capabilities (key, name, description, metadata) VALUES
  ('request.planning', 'Request planning', 'Break an engineering request into steps', '{"group":"core"}'),
  ('project.context.read', 'Project context', 'Read project model, memory and files', '{"group":"core"}'),
  ('document.interpret', 'Document interpretation', 'Read uploaded drawings, PDFs and spreadsheets', '{"group":"core"}'),
  ('human.approval.enforced', 'Engineer approval', 'Results need engineer sign-off', '{"group":"core"}'),
  ('frame3d.analysis', '3D frame analysis', 'Deterministic 3D frame solver (gravity, modal, seismic)', '{"group":"analysis"}'),
  ('seismic.iran2800', 'Iran 2800 seismic', 'Standard 2800 equivalent static and modal checks', '{"group":"analysis"}'),
  ('design.mabhas9', 'Mabhas 9 RC design', 'Iranian National Building Code Part 9 concrete design', '{"group":"design"}'),
  ('design.aci318', 'ACI 318 checks', 'ACI 318 member checks', '{"group":"design"}'),
  ('design.aisc360', 'AISC 360 steel checks', 'AISC 360 steel beam checks', '{"group":"design"}'),
  ('rebar.detailing', 'Rebar detailing (DXF)', 'Beam/column rebar drawings and bar bending schedule', '{"group":"drawing"}'),
  ('report.generate', 'Engineering report', 'Generate calculation reports', '{"group":"report"}'),
  ('validation.run', 'Model validation', 'Run project validation rules', '{"group":"qa"}')
ON CONFLICT (key) DO NOTHING;
