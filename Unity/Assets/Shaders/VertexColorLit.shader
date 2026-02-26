// ============================================================================
// Game1 Vertex Color Lit Shader
// Renders mesh vertex colors with Unity Standard lighting.
// Used by terrain chunks, cliff edges, and entity primitives.
// Compatible with Built-in Render Pipeline (Surface Shader).
// URP compatibility: Unity auto-upgrades surface shaders in URP mode.
//
// Terrain detail: procedural noise pattern using world-space position adds
// visual texture so the ground feels solid underfoot, not flat/floating.
// ============================================================================

Shader "Game1/VertexColorLit"
{
    Properties
    {
        _Color ("Tint", Color) = (1,1,1,1)
        _Glossiness ("Smoothness", Range(0,1)) = 0.1
        _Metallic ("Metallic", Range(0,1)) = 0.0
        _DetailStrength ("Detail Strength", Range(0,0.5)) = 0.15
        _DetailScale ("Detail Scale", Range(1,50)) = 12.0
        _DetailScale2 ("Detail Scale (fine)", Range(10,100)) = 35.0
    }

    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        LOD 200

        CGPROGRAM
        #pragma surface surf Standard fullforwardshadows vertex:vert
        #pragma target 3.0
        #pragma multi_compile_instancing

        fixed4 _Color;
        half _Glossiness;
        half _Metallic;
        half _DetailStrength;
        half _DetailScale;
        half _DetailScale2;

        struct Input
        {
            fixed4 vertColor;
            float3 worldPos;
        };

        void vert(inout appdata_full v, out Input o)
        {
            UNITY_INITIALIZE_OUTPUT(Input, o);
            o.vertColor = v.color;
        }

        // Hash-based noise for procedural detail (no texture sampler needed)
        float hash21(float2 p)
        {
            p = frac(p * float2(123.34, 456.21));
            p += dot(p, p + 45.32);
            return frac(p.x * p.y);
        }

        // Value noise with smooth interpolation
        float valueNoise(float2 p)
        {
            float2 i = floor(p);
            float2 f = frac(p);
            f = f * f * (3.0 - 2.0 * f); // smoothstep

            float a = hash21(i);
            float b = hash21(i + float2(1, 0));
            float c = hash21(i + float2(0, 1));
            float d = hash21(i + float2(1, 1));

            return lerp(lerp(a, b, f.x), lerp(c, d, f.x), f.y);
        }

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            fixed4 c = IN.vertColor * _Color;

            // Procedural terrain detail using world XZ position
            float2 wuv = IN.worldPos.xz;

            // Two octaves of value noise for natural-looking ground texture
            float n1 = valueNoise(wuv * _DetailScale) * 2.0 - 1.0;     // coarse (-1..1)
            float n2 = valueNoise(wuv * _DetailScale2) * 2.0 - 1.0;    // fine   (-1..1)
            float detail = n1 * 0.7 + n2 * 0.3;

            // Modulate albedo: darken/lighten slightly for ground texture feel
            c.rgb += c.rgb * detail * _DetailStrength;

            // Micro-surface bump via tangent-space normal perturbation
            float eps = 0.05;
            float nx = valueNoise((wuv + float2(eps, 0)) * _DetailScale) -
                       valueNoise((wuv - float2(eps, 0)) * _DetailScale);
            float nz = valueNoise((wuv + float2(0, eps)) * _DetailScale) -
                       valueNoise((wuv - float2(0, eps)) * _DetailScale);
            o.Normal = normalize(float3(nx * 0.4, nz * 0.4, 1.0));

            o.Albedo = saturate(c.rgb);
            o.Metallic = _Metallic;
            o.Smoothness = _Glossiness;
            o.Alpha = 1.0;
        }
        ENDCG
    }

    FallBack "Diffuse"
}
