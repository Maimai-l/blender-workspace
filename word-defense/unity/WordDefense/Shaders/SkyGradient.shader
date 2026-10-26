// Soft three-colour sky with a sun glow, used as the skybox (no fog, drawn behind everything).
Shader "WordDefense/SkyGradient"
{
    Properties
    {
        _Top ("Top", Color) = (0.52, 0.76, 0.95, 1)
        _Horizon ("Horizon", Color) = (0.98, 0.91, 0.82, 1)
        _Mid ("Below Mid", Color) = (0.81, 0.89, 0.95, 1)
        _Bottom ("Below Deep", Color) = (0.65, 0.79, 0.91, 1)
        _SunDir ("Sun Direction", Vector) = (0.4, 0.25, 0.85, 0)
        _SunColor ("Sun Glow", Color) = (1, 0.93, 0.78, 1)
        _SunSize ("Sun Glow Size", Float) = 6
    }
    SubShader
    {
        Tags { "Queue"="Background" "RenderType"="Background" "PreviewType"="Skybox" "RenderPipeline"="UniversalPipeline" }
        Cull Off ZWrite Off
        Pass
        {
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            struct Attributes { float4 positionOS : POSITION; };
            struct Varyings { float4 positionCS : SV_POSITION; float3 dir : TEXCOORD0; };
            CBUFFER_START(UnityPerMaterial)
                half4 _Top; half4 _Horizon; half4 _Mid; half4 _Bottom; float4 _SunDir; half4 _SunColor; float _SunSize;
            CBUFFER_END
            Varyings vert(Attributes i)
            {
                Varyings o;
                o.positionCS = TransformObjectToHClip(i.positionOS.xyz);
                o.dir = i.positionOS.xyz;
                return o;
            }
            half4 frag(Varyings i) : SV_Target
            {
                float3 d = normalize(i.dir);
                float y = d.y;
                half3 c;
                if (y > 0) c = lerp(_Horizon.rgb, _Top.rgb, pow(saturate(y), 0.55));
                else
                {
                    // the game camera looks down, so most of the visible sky is below the horizon
                    float k = saturate((-y - 0.3) / 0.5);
                    c = k < 0.5 ? lerp(_Horizon.rgb, _Mid.rgb, smoothstep(0.0, 1.0, k * 2.0)) : lerp(_Mid.rgb, _Bottom.rgb, smoothstep(0.0, 1.0, k * 2.0 - 1.0));
                }
                float s = saturate(dot(d, normalize(_SunDir.xyz)));
                c += _SunColor.rgb * pow(s, _SunSize) * 0.35;
                return half4(c, 1);
            }
            ENDHLSL
        }
    }
}
