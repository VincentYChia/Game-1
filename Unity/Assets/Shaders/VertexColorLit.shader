// ============================================================================
// Game1 Vertex Color Lit Shader
// Renders mesh vertex colors with Unity Standard lighting.
// Used by terrain chunks, cliff edges, and entity primitives.
// Compatible with Built-in Render Pipeline (Surface Shader).
// URP compatibility: Unity auto-upgrades surface shaders in URP mode.
// ============================================================================

Shader "Game1/VertexColorLit"
{
    Properties
    {
        _Color ("Tint", Color) = (1,1,1,1)
        _Glossiness ("Smoothness", Range(0,1)) = 0.1
        _Metallic ("Metallic", Range(0,1)) = 0.0
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

        struct Input
        {
            fixed4 vertColor;
        };

        void vert(inout appdata_full v, out Input o)
        {
            UNITY_INITIALIZE_OUTPUT(Input, o);
            o.vertColor = v.color;
        }

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            fixed4 c = IN.vertColor * _Color;
            o.Albedo = c.rgb;
            o.Metallic = _Metallic;
            o.Smoothness = _Glossiness;
            o.Alpha = 1.0;
        }
        ENDCG
    }

    FallBack "Diffuse"
}
